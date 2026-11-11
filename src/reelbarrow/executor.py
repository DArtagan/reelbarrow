"""The executor: an automatic plan carried out on the share, or refused.

`Writer` is the one place anything under the video root is changed, and the
one place dry run is checked (*Rules that protect the library*, in
`AGENTS.md`). While `dry_run` is true it refuses every change before touching
the share, and the executor reports each as refused; the deployment also
mounts the share read-only while dry run is on, so a bug here meets `EROFS`.
No other module writes under the video root, which `tests/test_write_guard.py`
holds; the manifest exporter, which never mounts the library, writes only in
its own output directory.

Carrying out a plan is step 7 of *The service*, in the design:

1. The ledger is asked first: a unit it has an entry for is never filed again.
2. The plan's basis is compared with the share. If anything differs, nothing
   is done, and the manifest is planned again.
3. Every sidecar is rendered, so a provider that can't be reached stops the
   filing before anything has moved.
4. The operations, in the plan's order: folders and renames, then sidecars,
   then leftovers. The ledger's entry is opened before the first and updated
   after each. If one fails, the rest aren't attempted and the entry says
   `incomplete`, with what was done; nothing is undone automatically.
5. The entry is closed as `filed`.
6. Plex scans each film folder touched, since its own change detection can't
   be relied on over CIFS.
"""

import os
import sqlite3
import stat
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, ConfigDict

from reelbarrow.fanart import FanartError
from reelbarrow.ledger import Ledger, LedgerError, State
from reelbarrow.manifest import Manifest, ShareRef
from reelbarrow.plan import (
    Basis,
    DeleteFolder,
    Gate,
    MakeFolder,
    Operation,
    PathState,
    Plan,
    Rename,
    ShareLibrary,
    Write,
    manifest_sha256,
)
from reelbarrow.plex import Plex, PlexError
from reelbarrow.sidecars import Rendered, SidecarError, Sources, render
from reelbarrow.tmdb import TmdbError


class Refused(Exception):
    """Dry run is on: nothing on the share is changed."""


class WriterError(Exception):
    """The share isn't as the operation needs it, so it isn't attempted."""


class Writer:
    """Every change under the video root: make a folder, rename, write a new
    file, remove an emptied folder. Nothing is ever overwritten, copied or
    removed with what it holds."""

    def __init__(self, video_root: Path, *, dry_run: bool = True) -> None:
        self.video_root = video_root
        self.dry_run = dry_run

    def _refuse_in_dry_run(self) -> None:
        if self.dry_run:
            raise Refused("dry run")

    def _path(self, path: str) -> Path:
        """This process's path to an entry, its own name unresolved, so a
        link is acted on as itself; a link among its folders is refused."""
        share = PurePosixPath(ShareRef(path=path).path)
        root = self.video_root.resolve()
        parent = (root / share.parent).resolve()
        if parent != root / share.parent:
            raise WriterError(f"{path}: a folder above it is a link")
        return parent / share.name

    def make_folder(self, path: str) -> None:
        self._refuse_in_dry_run()
        try:
            os.mkdir(self._path(path))
        except FileExistsError as error:
            raise WriterError(f"{path} is already there") from error

    def rename(self, source: str, target: str) -> None:
        """Within the share's one filesystem, onto nothing."""
        self._refuse_in_dry_run()
        old, new = self._path(source), self._path(target)
        found = os.lstat(old)
        if not (stat.S_ISREG(found.st_mode) or stat.S_ISDIR(found.st_mode)):
            raise WriterError(f"{source} is neither a file nor a folder")
        # rename() replaces a file silently. The basis was compared moments
        # ago and one worker files, so checking here, just before, is enough.
        if os.path.lexists(new):
            raise WriterError(f"{target} is already there")
        if os.lstat(new.parent).st_dev != found.st_dev:
            raise WriterError(f"{source} and {target} are on different filesystems")
        os.rename(old, new)

    def write(self, path: str, content: bytes) -> None:
        """A new file; refused if anything is at its path."""
        self._refuse_in_dry_run()
        target = self._path(path)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
        try:
            fd = os.open(target, flags, 0o666)
        except FileExistsError as error:
            raise WriterError(f"{path} is already there") from error
        try:
            view = memoryview(content)
            while view:
                view = view[os.write(fd, view) :]
            os.fsync(fd)
        except BaseException:
            os.close(fd)
            os.unlink(target)
            raise
        os.close(fd)

    def delete_folder(self, path: str) -> None:
        """An empty folder; one holding anything is refused by the
        filesystem."""
        self._refuse_in_dry_run()
        folder = self._path(path)
        if not stat.S_ISDIR(os.lstat(folder).st_mode):
            raise WriterError(f"{path} isn't a folder")
        os.rmdir(folder)


class Outcome(StrEnum):
    DONE = "done"
    # Dry run: not attempted.
    REFUSED = "refused"
    FAILED = "failed"
    # A step before it failed.
    NOT_RUN = "not_run"
    # Nothing to do: an artwork neither provider has.
    SKIPPED = "skipped"


class Result(StrEnum):
    FILED = "filed"
    # Dry run: every change refused, the share as it was.
    DRY_RUN = "dry_run"
    # An operation failed part way; the ledger says what was done.
    INCOMPLETE = "incomplete"
    # Nothing done, and the manifest is to be planned again.
    BASIS_CHANGED = "basis_changed"
    # A sidecar couldn't be rendered, so nothing was done.
    NOT_RENDERED = "not_rendered"
    # The ledger has an entry for the unit, so nothing was done.
    IN_LEDGER = "in_ledger"
    # The ledger couldn't be opened for it, so nothing was done.
    NOT_STARTED = "not_started"


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Step(Model):
    step: str
    subject: str
    outcome: Outcome
    detail: str


class Report(Model):
    source: str
    id: str
    result: Result
    steps: list[Step]

    def to_json(self) -> dict:
        return self.model_dump(mode="json")

    @property
    def succeeded(self) -> bool:
        return self.result in (Result.FILED, Result.DRY_RUN) and not any(
            step.outcome is Outcome.FAILED for step in self.steps
        )


def differences(
    basis: Basis, manifest: Manifest, stat_path: Callable[[str], PathState]
) -> list[str]:
    """What of a plan's basis the share and the manifest no longer match."""
    found = []
    if manifest_sha256(manifest) != basis.manifest_sha256:
        found.append("the manifest")
    for planned in basis.paths:
        now = stat_path(planned.path)
        if now.present != planned.present:
            found.append(f"{planned.path} {'appeared' if now.present else 'went'}")
        elif planned.present and (
            (planned.size is not None and now.size != planned.size)
            or (planned.mtime is not None and now.mtime != planned.mtime)
        ):
            found.append(f"{planned.path} changed")
    return found


def _subject(op: Operation) -> str:
    match op:
        case Rename():
            return f"{op.source} -> {op.target}"
        case _:
            return op.path


class Executor:
    def __init__(
        self,
        writer: Writer,
        ledger: Ledger,
        sources: Sources,
        libraries: Sequence[str],
        plex: Plex | None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.writer = writer
        self.ledger = ledger
        self.sources = sources
        self.libraries = list(libraries)
        self.plex = plex
        self.clock = clock

    def carry_out(self, plan: Plan, manifest: Manifest) -> Report:
        if plan.gate is not Gate.AUTOMATIC:
            raise ValueError(f"{plan.source} {plan.id} is for {plan.gate}")
        if (manifest.source, manifest.id) != (plan.source, plan.id):
            raise ValueError(f"{manifest.id}'s manifest, not {plan.id}'s")

        steps: list[Step] = []

        def report(result: Result) -> Report:
            return Report(source=plan.source, id=plan.id, result=result, steps=steps)

        def step(name: str, outcome: Outcome, detail: str) -> Step:
            return Step(step=name, subject=plan.id, outcome=outcome, detail=detail)

        entry = self.ledger.entry(plan.source, plan.id)
        if entry is not None:
            detail = f"entered as {entry.state} on {entry.started:%Y-%m-%d}"
            steps.append(step("ledger", Outcome.NOT_RUN, detail))
            return report(Result.IN_LEDGER)

        # The planner's own measure of a path, so the two compare exactly.
        stat_path = ShareLibrary(self.writer.video_root, "").stat
        changed = differences(plan.basis, manifest, stat_path)
        if changed:
            detail = f"changed since planned: {', '.join(changed)}"
            steps.append(step("basis", Outcome.FAILED, detail))
            return report(Result.BASIS_CHANGED)
        detail = f"the manifest and {len(plan.basis.paths)} paths as planned"
        steps.append(step("basis", Outcome.DONE, detail))

        rendered: dict[int, Rendered] = {}
        try:
            for index, op in enumerate(plan.operations):
                if isinstance(op, Write):
                    rendered[index] = render(op, self.sources)
        except (SidecarError, TmdbError, FanartError) as error:
            steps.append(step("sidecars", Outcome.FAILED, str(error)))
            return report(Result.NOT_RENDERED)

        operations = [
            Step(
                step=op.op,
                subject=_subject(op),
                outcome=Outcome.NOT_RUN,
                detail=op.reason,
            )
            for op in plan.operations
        ]

        def outcomes() -> list[dict]:
            return [operation.model_dump(mode="json") for operation in operations]

        live = not self.writer.dry_run
        if live:
            try:
                self.ledger.begin(plan, self.clock(), outcomes())
            except (LedgerError, sqlite3.Error) as error:
                steps.append(step("ledger", Outcome.FAILED, str(error)))
                return report(Result.NOT_STARTED)

        failed = False
        try:
            for index, op in enumerate(plan.operations):
                outcome, detail = self._apply(op, rendered.get(index))
                planned = operations[index]
                operations[index] = planned.model_copy(
                    update={
                        "outcome": outcome,
                        "detail": f"{planned.detail}: {detail}"
                        if detail
                        else planned.detail,
                    }
                )
                if live:
                    self.ledger.update(plan.source, plan.id, outcomes())
                if outcome is Outcome.FAILED:
                    failed = True
                    break
            if live:
                state = State.INCOMPLETE if failed else State.FILED
                self.ledger.update(
                    plan.source, plan.id, outcomes(), state, self.clock()
                )
                ledger = step("ledger", Outcome.DONE, f"entered as {state}")
            else:
                ledger = step("ledger", Outcome.REFUSED, "dry run")
        except (LedgerError, sqlite3.Error) as error:
            # Nothing more is done that the ledger can't record.
            steps += [*operations, step("ledger", Outcome.FAILED, str(error))]
            return report(Result.INCOMPLETE)
        steps += [*operations, ledger]
        if failed:
            return report(Result.INCOMPLETE)

        steps += [self._scan(folder) for folder in self._touched(plan)]
        return report(Result.FILED if live else Result.DRY_RUN)

    def _apply(self, op: Operation, rendered: Rendered | None) -> tuple[Outcome, str]:
        detail = rendered.detail if rendered is not None else ""
        try:
            match op:
                case MakeFolder():
                    self.writer.make_folder(op.path)
                case Rename():
                    self.writer.rename(op.source, op.target)
                case Write():
                    assert rendered is not None
                    if rendered.content is None:
                        return Outcome.SKIPPED, detail
                    self.writer.write(op.path, rendered.content)
                case DeleteFolder():
                    self.writer.delete_folder(op.path)
        except Refused:
            return Outcome.REFUSED, detail
        except (WriterError, OSError, ValueError) as error:
            return Outcome.FAILED, str(error)
        return Outcome.DONE, detail

    def _touched(self, plan: Plan) -> list[str]:
        """Each folder directly in a library that an operation writes into."""
        folders: dict[str, None] = {}
        for op in plan.operations:
            path = op.target if isinstance(op, Rename) else op.path
            if isinstance(op, DeleteFolder):
                continue
            for library in self.libraries:
                if path.startswith(f"{library}/"):
                    name = path[len(library) + 1 :].split("/")[0]
                    folders[f"{library}/{name}"] = None
        return list(folders)

    def _scan(self, folder: str) -> Step:
        def step(outcome: Outcome, detail: str) -> Step:
            return Step(
                step="plex_scan", subject=folder, outcome=outcome, detail=detail
            )

        if self.writer.dry_run:
            return step(Outcome.REFUSED, "dry run")
        if self.plex is None:
            return step(Outcome.FAILED, "Plex isn't configured")
        try:
            return step(Outcome.DONE, self.plex.scan(folder))
        except PlexError as error:
            return step(Outcome.FAILED, str(error))


def render_report(report: Report) -> str:
    """A report as a person reads it."""
    lines = [f"{report.source} {report.id}: {report.result}"]
    for step in report.steps:
        lines.append(f"  {step.outcome:<8} {step.step:<13} {step.subject}")
        lines.append(f"  {'':<8} {'':<13} {step.detail}")
    return "\n".join(lines)
