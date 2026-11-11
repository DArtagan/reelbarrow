"""Classify, identify, plan and gate: what one manifest's unit of work becomes.

Steps 3-6 of *The service* in the design, built as far as a film whose
completed folder holds its feature alone, and whose raw copy is that title's
MKV. Everything else plans for review, with the checks that say why, so no
case the rules don't yet cover can file itself. A plan is all or nothing: one
failed check sends the whole plan to review (*Confidence*).

The planner reads the manifest, its analysis (`reelbarrow.analyse`) and the
library, and measures nothing itself, so a fixture plans exactly as the share
does.
"""

import hashlib
import json
import os
from collections.abc import Sequence
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal, Protocol

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from reelbarrow import disc_record, names
from reelbarrow.analyse import Analysis, File, Folder, Video
from reelbarrow.disc_record import (
    DiscRecord,
    FiledFrom,
    FiledRaw,
    FiledRef,
    FiledTitle,
    Film,
)
from reelbarrow.intake import RawFound
from reelbarrow.manifest import IdentityReason, Manifest, RawForm, ShareRef, State
from reelbarrow.tmdb import Movie, Tmdb

SCHEMA = 1

# A film's feature is the one title within this fraction of TMDB's runtime
# (*Confidence*, this disc is film X). A starting point: the evaluation sets it.
RUNTIME_TOLERANCE = 0.03
# A DVD title's MKV and its transcode, in length and at each chapter's start
# (*Confidence*, a transcode is raw title X). MakeMKV's MKV is HandBrake's
# source, and a transcode's length equals its MKV's to the millisecond (E33).
PAIRING_TOLERANCE = 0.25
# HandBrake drops a chapter that starts this close to a title's end, from an
# MKV as from a Blu-ray playlist (E35): job 34's MKV has one at 1.03 s before
# its end, and its transcode, of equal length, doesn't.
HANDBRAKE_LAST_CHAPTER = 1.5

# Who identified the disc, for this disc is film X: ARM's own lookup, or a
# person in its UI. An identity ARM copied from another job by label is not
# an identification (*What ARM knows*).
IDENTIFIED_BY = frozenset({IdentityReason.LOOKUP, IdentityReason.SET_BY_PERSON})

# Kodi's names, which every player that reads artwork reads (*Sidecars and
# embedded metadata*). Each is written where TMDB or fanart.tv has it.
ARTWORK = (
    "poster.jpg",
    "fanart.jpg",
    "clearlogo.png",
    "clearart.png",
    "landscape.jpg",
    "disc.png",
)
# Kept out of Jellyfin's and Kodi's scans; the library's .plexignore covers
# Plex's.
IGNORE_MARKERS = (".ignore", ".nomedia")


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Gate(StrEnum):
    # Every check passed: it files without a person.
    AUTOMATIC = "automatic"
    # A person can decide it now, from what the plan shows.
    REVIEW = "review"
    # No one can decide it until something else is ripped.
    HOLD = "hold"


class Check(Model):
    rule: str
    passed: bool
    detail: str


class Sidecar(StrEnum):
    MOVIE_NFO = "movie_nfo"
    ARTWORK = "artwork"
    IGNORE_MARKER = "ignore_marker"
    DISC_JSON = "disc_json"


class MakeFolder(Model):
    op: Literal["make_folder"] = "make_folder"
    path: str
    reason: str


class Rename(Model):
    op: Literal["rename"] = "rename"
    source: str
    target: str
    reason: str


class Write(Model):
    op: Literal["write"] = "write"
    path: str
    sidecar: Sidecar
    reason: str
    content: dict | None = Field(
        default=None,
        description="What it holds: a document written as it stands, or for a "
        "sidecar rendered from a source, which record. Null: an empty file.",
    )


class DeleteFolder(Model):
    """A folder the operations before it have emptied."""

    op: Literal["delete_folder"] = "delete_folder"
    path: str
    reason: str


Operation = Annotated[
    MakeFolder | Rename | Write | DeleteFolder, Field(discriminator="op")
]


class PathState(Model):
    path: str
    present: bool
    size: int | None = None
    mtime: AwareDatetime | None = None


class Basis(Model):
    """What the plan was made from: if any of it differs when the plan is
    carried out, nothing is done and the manifest is planned again."""

    manifest_sha256: str
    paths: list[PathState] = Field(
        description="Every path it reads, and every library path it writes, "
        "renames onto or deletes, absent ones included."
    )


class Plan(Model):
    schema_: Literal[1] = Field(alias="schema", default=SCHEMA)
    source: str
    id: str
    gate: Gate
    checks: list[Check]
    operations: list[Operation]
    record: str | None = Field(
        default=None,
        description="Where the executor writes the filing's record: what it "
        "was given and what each operation did. Null: the plan has no place "
        "for one, so it is never carried out.",
    )
    basis: Basis

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    def to_json(self) -> dict:
        return self.model_dump(mode="json", by_alias=True)


class Library(Protocol):
    def movie_folders(self) -> Sequence[str]:
        """The names of the film library's folders."""
        ...

    def stat(self, path: str) -> PathState: ...


class ShareLibrary:
    """The library as it stands on the share."""

    def __init__(self, video_root: Path, movies: str) -> None:
        self.video_root = video_root
        self.movies = movies

    def movie_folders(self) -> list[str]:
        top = ShareRef(path=self.movies).resolve(self.video_root)
        return sorted(p.name for p in top.iterdir() if p.is_dir())

    def stat(self, path: str) -> PathState:
        try:
            stat = os.stat(self.video_root / PurePosixPath(path), follow_symlinks=False)
        except FileNotFoundError:
            return PathState(path=path, present=False)
        return PathState(
            path=path,
            present=True,
            size=stat.st_size,
            mtime=datetime.fromtimestamp(stat.st_mtime, UTC),
        )


def manifest_sha256(job: Manifest) -> str:
    """Of its content, not its bytes, so a copy reformatted is the same."""
    canonical = json.dumps(job.to_json(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def chapter_starts(video: Video) -> list[float]:
    # An MKV with one chapter lists none, and it starts at 0.
    return video.chapters or [0.0]


def pairing(source: Video, transcode: Video) -> tuple[bool, str]:
    """Whether a DVD title's MKV is a transcode's source: equal in length and
    in every chapter's start."""
    length = abs(source.duration - transcode.duration)
    ours, theirs = chapter_starts(source), chapter_starts(transcode)
    stub = ""
    if (
        len(ours) == len(theirs) + 1
        and source.duration - ours[-1] < HANDBRAKE_LAST_CHAPTER
    ):
        stub = f", and the source's last, {source.duration - ours[-1]:.2f} s from"
        stub += " its end, which HandBrake drops"
        ours = ours[:-1]
    if len(ours) != len(theirs):
        return False, f"{len(ours)} chapters against {len(theirs)}"
    worst = max(abs(a - b) for a, b in zip(ours, theirs, strict=True))
    detail = (
        f"lengths {length:.3f} s apart, {len(ours)} chapters within {worst:.3f} s"
        + stub
    )
    return length <= PAIRING_TOLERANCE and worst <= PAIRING_TOLERANCE, detail


class _Checks:
    def __init__(self) -> None:
        self.checks: list[Check] = []

    def __call__(self, rule: str, passed: bool, detail: str) -> bool:
        self.checks.append(Check(rule=rule, passed=passed, detail=detail))
        return passed

    @property
    def all_passed(self) -> bool:
        return all(check.passed for check in self.checks)


def _minutes(seconds: float) -> str:
    return f"{seconds / 60:.1f} min"


def _entries(folder: Folder) -> list[PathState]:
    states = [PathState(path=folder.path, present=True, mtime=folder.mtime)]
    states += [
        PathState(path=f.path, present=True, mtime=f.mtime) for f in folder.folders
    ]
    states += [
        PathState(path=f.path, present=True, size=f.size, mtime=f.mtime)
        for f in folder.files
    ]
    return states


def plan(
    job: Manifest,
    analysis: Analysis,
    tmdb: Tmdb,
    library: Library,
    movies: str = "movies",
) -> Plan:
    if (analysis.source, analysis.id) != (job.source, job.id):
        raise ValueError(f"{analysis.source} {analysis.id}'s analysis, not {job.id}'s")
    check = _Checks()
    operations: list[Operation] = []
    filing_record: str | None = None

    check("state", job.state is State.SUCCEEDED, f"the job {job.state}")
    check(
        "recorded paths",
        not analysis.missing,
        "every path the manifest records is on the share"
        if not analysis.missing
        else f"not on the share: {', '.join(analysis.missing)}",
    )

    # Classify: the completed folder's videos.
    videos: list[File] = []
    completed = analysis.completed
    if completed is not None:
        videos = [f for f in completed.files if f.is_video]
        others = [f.name for f in completed.files if not f.is_video]
        unread = [f.name for f in videos if f.video is None]
        check(
            "completed folder",
            bool(videos) and not others and not unread,
            f"{len(videos)} videos"
            + (f"; besides them {', '.join(others)}" if others else "")
            + (f"; not measured: {', '.join(unread)}" if unread else ""),
        )
    else:
        check("completed folder", False, "none to file")

    # Identify: ARM's IMDb id to TMDB, checked against the feature's runtime.
    movie = _identify(job, tmdb, check)
    feature = None
    if movie is not None and movie.runtime:
        feature = _feature(videos, movie, check)

    disc = job.disc
    check(
        "disc identity",
        disc is not None and disc.type == "dvd" and disc.crc64 is not None,
        f"a DVD, CRC64 {disc.crc64}"
        if disc is not None and disc.type == "dvd" and disc.crc64
        else "only a DVD with its CRC64 is planned yet",
    )

    raw_source = _raw(job, analysis, feature, check)

    paths: list[PathState] = []
    if completed is not None:
        paths += _entries(completed)
    for folder in analysis.raw:
        paths += _entries(folder)

    if movie is not None and feature is not None and movie.year is not None:
        title = names.fold(movie.title)
        try:
            if not title.strip(". "):
                raise names.UnwritableName(
                    f"nothing of {movie.title!r} can be written to the share"
                )
            film = names.component(f"{title} ({movie.year})")
        except names.UnwritableName as error:
            check("name", False, str(error))
        else:
            check("name", True, f"{film!r}, from TMDB's {movie.title!r}")
            operations, targets, filing_record = _operations(
                job, movie, film, movies, completed, feature, raw_source
            )
            states = [library.stat(path) for path in targets]
            there = [state.path for state in states if state.present]
            check(
                "library",
                not there and not _already_filed(library, film, movie.id),
                f"already there: {', '.join(there)}"
                if there
                else (
                    f"the library already holds {film} or TMDB {movie.id}"
                    if _already_filed(library, film, movie.id)
                    else f"{film} isn't in the library"
                ),
            )
            paths += states

    gate = Gate.AUTOMATIC if check.all_passed else Gate.REVIEW
    return Plan(
        source=job.source,
        id=job.id,
        gate=gate,
        checks=check.checks,
        operations=operations,
        record=filing_record,
        basis=Basis(manifest_sha256=manifest_sha256(job), paths=paths),
    )


def _identify(job: Manifest, tmdb: Tmdb, check: _Checks) -> Movie | None:
    identity = job.identity
    if not check(
        "kind",
        identity is not None and identity.kind.value == "movie",
        f"ARM says {identity.kind.value}"
        if identity is not None
        else "the manifest records no identity",
    ):
        return None
    assert identity is not None
    imdb = identity.imdb_id
    if not check(
        "identified",
        bool(imdb.value) and imdb.reason in IDENTIFIED_BY,
        f"IMDb {imdb.value}, by {imdb.reason}"
        if imdb.value
        else f"no IMDb id ({imdb.reason})",
    ):
        return None
    assert imdb.value is not None
    ids = tmdb.movie_ids_for_imdb(imdb.value)
    if not check(
        "tmdb",
        len(ids) == 1,
        f"TMDB has {len(ids)} films for {imdb.value}"
        if len(ids) != 1
        else f"{imdb.value} is TMDB {ids[0]}",
    ):
        return None
    movie = tmdb.movie(ids[0])
    check(
        "tmdb record",
        bool(movie.runtime) and movie.year is not None,
        f"{movie.title!r}, {movie.year}, {movie.runtime} min",
    )
    return movie


def _feature(videos: list[File], movie: Movie, check: _Checks) -> File | None:
    assert movie.runtime
    runtime = movie.runtime * 60
    measured = [f for f in videos if f.video is not None]

    def off(file: File) -> float:
        assert file.video is not None
        return file.video.duration / runtime - 1

    near = [f for f in measured if abs(off(f)) <= RUNTIME_TOLERANCE]
    lengths = ", ".join(
        f"{f.name} {_minutes(f.video.duration)} ({off(f):+.1%})"
        for f in measured
        if f.video is not None
    )
    if not check(
        "runtime",
        len(near) == 1,
        f"{len(near)} of {lengths or 'no titles'} within"
        f" {RUNTIME_TOLERANCE:.0%} of TMDB's {movie.runtime} min",
    ):
        return None
    (feature,) = near
    rest = [f.name for f in videos if f is not feature]
    check(
        "extras",
        not rest,
        "the feature alone"
        if not rest
        else f"other titles, not yet classified: {', '.join(rest)}",
    )
    return feature


def _raw(
    job: Manifest, analysis: Analysis, feature: File | None, check: _Checks
) -> list[File]:
    """The raw folder's MKVs, if they are the feature's source and nothing
    else."""
    if job.raw is not None:
        check("raw copy", False, f"a recorded {job.raw.form} isn't planned yet")
        return []
    found = [f for f in analysis.raw if f.found is RawFound.WRITTEN_DURING_RUN]
    if not check(
        "raw copy",
        len(found) == 1,
        "no MKV was written while the job ran"
        if not found
        else (
            f"MKVs written while the job ran in {len(found)} folders: "
            + ", ".join(f.path for f in found)
            if len(found) > 1
            else f"{found[0].path}, written while the job ran"
        ),
    ):
        return []
    (folder,) = found
    files = folder.files
    unpaired = [
        f.name
        for f in files
        if f.video is None or PurePosixPath(f.path).suffix.lower() != ".mkv"
    ]
    if not check(
        "raw folder",
        bool(files) and not unpaired and not folder.folders,
        f"{len(files)} MKVs"
        + (f"; besides them {', '.join(unpaired)}" if unpaired else "")
        + (
            f"; folders {', '.join(f.path for f in folder.folders)}"
            if folder.folders
            else ""
        ),
    ):
        return []
    if feature is None or feature.video is None:
        return []
    if len(files) != 1:
        check("pairing", False, f"{len(files)} MKVs for one transcode")
        return []
    (source,) = files
    assert source.video is not None
    paired, detail = pairing(source.video, feature.video)
    check("pairing", paired, f"{source.name} is {feature.name}'s source: {detail}")
    return files if paired else []


def _already_filed(library: Library, film: str, tmdb_id: int) -> bool:
    """A folder for this film by its name or its TMDB id: filing into it is
    case 9, folding, which isn't planned yet."""
    tag = f"{{tmdb-{tmdb_id}}}"
    return any(
        name == film or name.startswith(f"{film} {{") or name.endswith(tag)
        for name in library.movie_folders()
    )


def _operations(
    job: Manifest,
    movie: Movie,
    film: str,
    movies: str,
    completed: Folder | None,
    feature: File,
    raw_source: list[File],
) -> tuple[list[Operation], list[str], str | None]:
    """The operations, in the order the executor carries them out: folders,
    then renames, then sidecars, then leftovers; their target paths; and where
    the filing's record goes.

    Every folder is made before anything moves, so once anything has, the
    disc's folder is there for the record of what was done."""
    assert job.disc is not None
    folder = f"{movies}/{film} {{tmdb-{movie.id}}}"
    target = f"{folder}/{film}{PurePosixPath(feature.path).suffix}"
    runtime = f"TMDB's {movie.runtime} min"
    filing_record = None
    folders: list[Operation] = [
        MakeFolder(path=folder, reason=f"{movie.title}'s folder, TMDB {movie.id}"),
    ]
    renames: list[Operation] = [
        Rename(
            source=feature.path,
            target=target,
            reason=f"the feature: {_minutes(feature.video.duration)} against {runtime}"
            if feature.video
            else "the feature",
        ),
    ]
    sidecars: list[Operation] = [
        Write(
            path=f"{folder}/movie.nfo",
            sidecar=Sidecar.MOVIE_NFO,
            reason="the identification, for players other than Plex",
            content={"tmdb_id": movie.id, "imdb_id": movie.imdb_id},
        ),
        *(
            Write(
                path=f"{folder}/{name}",
                sidecar=Sidecar.ARTWORK,
                reason="artwork, where TMDB or fanart.tv has it",
                content={"tmdb_id": movie.id, "kind": PurePosixPath(name).stem},
            )
            for name in ARTWORK
        ),
    ]
    # A folder is a leftover only once every file in it has moved.
    leftovers: list[Operation] = []
    if completed is not None and [f.path for f in completed.files] == [feature.path]:
        leftovers += _emptied(completed, "the job's completed folder")
    if raw_source:
        assert job.disc.crc64 is not None
        label = names.component(job.disc.label or "DVD")
        raw = f"{folder}/raw"
        disc = f"{raw}/{label} [dvd-{job.disc.crc64}]"
        filing_record = f"{disc}/{record_name(job.source, job.id)}"
        folders += [
            MakeFolder(path=raw, reason="raw copies, one folder for each disc"),
            MakeFolder(
                path=disc, reason=f"disc {job.disc.label}, CRC64 {job.disc.crc64}"
            ),
        ]
        # Paired by content, so known by its MKV: a job from before the raw
        # copy's record has no disc number for it.
        filed = [
            FiledTitle(
                extracted=FiledRef(path=source.name),
                transcode=FiledRef(path=f"../../{PurePosixPath(target).name}"),
            )
            for source in raw_source
        ]
        disc_json = DiscRecord(
            schema=1,
            from_=FiledFrom(
                source=job.source, id=job.id, manifest_sha256=manifest_sha256(job)
            ),
            films=[Film(tmdb_id=movie.id, imdb_id=movie.imdb_id)],
            disc=job.disc,
            raw=FiledRaw(form=RawForm.MKV_TITLES),
            titles=filed,
        )
        for source in raw_source:
            renames.append(
                Rename(
                    source=source.path,
                    target=f"{disc}/{source.name}",
                    reason="the feature's source, written while the job ran",
                )
            )
        sidecars += [
            Write(
                path=f"{raw}/{marker}",
                sidecar=Sidecar.IGNORE_MARKER,
                reason="keeps the raw copies out of players' scans",
            )
            for marker in IGNORE_MARKERS
        ]
        sidecars.append(
            Write(
                path=f"{disc}/{disc_record.FILENAME}",
                sidecar=Sidecar.DISC_JSON,
                reason="the disc, the film, the job, and which raw title became "
                "which file",
                content=disc_json.to_json(),
            )
        )
        source_folder = PurePosixPath(raw_source[0].path).parent
        leftovers += [
            DeleteFolder(
                path=str(source_folder), reason="the job's raw folder, emptied"
            )
        ]
    operations = folders + renames + sidecars + leftovers
    targets = [
        path
        for op in operations
        for path in (
            [op.path]
            if isinstance(op, MakeFolder | Write)
            else [op.target]
            if isinstance(op, Rename)
            else []
        )
    ]
    if filing_record is not None:
        targets.append(filing_record)
    return operations, targets, filing_record


def record_name(source: str, id: str) -> str:
    """The filing record's name: one a unit, so several units filed into one
    disc's folder never meet."""
    return f"filing-{source}-{id}.json"


def _emptied(folder: Folder, what: str) -> list[DeleteFolder]:
    """A folder and those under it, deepest first."""
    under = sorted(
        (f.path for f in folder.folders), key=lambda p: p.count("/"), reverse=True
    )
    return [
        *(DeleteFolder(path=path, reason=f"inside {what}, emptied") for path in under),
        DeleteFolder(path=folder.path, reason=f"{what}, emptied"),
    ]


def render(plan: Plan) -> str:
    """A plan as a person reads it."""
    lines = [f"{plan.source} {plan.id}: {plan.gate}"]
    for check in plan.checks:
        lines.append(
            f"  {'ok  ' if check.passed else 'FAIL'} {check.rule}: {check.detail}"
        )
    for op in plan.operations:
        match op:
            case MakeFolder():
                lines.append(f"  make folder  {op.path}")
            case Rename():
                lines.append(f"  rename       {op.source}")
                lines.append(f"           to  {op.target}")
            case Write():
                lines.append(f"  write        {op.path}")
            case DeleteFolder():
                lines.append(f"  delete       {op.path}")
        lines.append(f"               {op.reason}")
    return "\n".join(lines)
