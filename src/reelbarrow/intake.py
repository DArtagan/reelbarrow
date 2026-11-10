"""Intake: where a manifest's unit of work is on the share.

Every path a manifest records is a claim, checked against the share and never
completed by matching names: `title_N` numbering and `_<stage>` suffixes change
between rips of one disc, and a raw folder keeps the name its job had when the
rip started. Intake finds files and measures nothing.

A job from before the raw copy's record (*The raw copy's record*, in the
design) doesn't say where its raw copy is. The copy is the one the job made:
the MKVs written into ARM's raw folder while the job ran, by their
modification time. That finds each rip's own copy where re-rips of one disc
share a label and a title, and a copy moved or rewritten since is not found,
which leaves it unfiled rather than misfiled. Content confirms the pairing;
the time only says where to look.
"""

import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath

from reelbarrow import manifest
from reelbarrow.manifest import Manifest, ShareRef


class RawFound(StrEnum):
    """How intake knows a raw folder is the job's."""

    # The manifest records it.
    RECORDED = "recorded"
    # It holds MKVs written while the job ran.
    WRITTEN_DURING_RUN = "written_during_run"


@dataclass(frozen=True, slots=True)
class RawFolder:
    path: str
    found: RawFound


@dataclass(frozen=True, slots=True)
class Location:
    """The folders a unit of work's files are in, by their share paths."""

    completed: str | None
    raw: tuple[RawFolder, ...]
    # Paths the manifest records that aren't on the share.
    missing: tuple[str, ...]


def read(path: Path) -> Manifest:
    return Manifest.model_validate_json(path.read_bytes())


def manifest_paths(path: Path) -> list[Path]:
    """A manifest file is itself; a folder is every manifest in it."""
    if path.is_dir():
        return sorted(path.glob(manifest.GLOB))
    return [path]


class RawIndex:
    """ARM's raw folders' top-level MKVs and when each was last written.

    Listed once and shared by every manifest a run plans: a stat of each file,
    not a read. Only the top level, where a DVD's per-title MKVs were written
    before images (*What a raw folder holds*). A Blu-ray backup and a DVD
    image are recorded by every job that made one since, and a Blu-ray from
    before is paired by its structure, which this doesn't find.
    """

    def __init__(self, video_root: Path, raw: str) -> None:
        self.raw = raw
        self._entries: list[tuple[str, datetime]] = []
        top = ShareRef(path=raw).resolve(video_root)
        if not top.is_dir():
            return
        for folder in sorted(top.iterdir()):
            if not folder.is_dir():
                continue
            for entry in sorted(folder.iterdir()):
                if entry.suffix.lower() == ".mkv" and entry.is_file():
                    mtime = datetime.fromtimestamp(entry.stat().st_mtime, UTC)
                    share = f"{raw}/{folder.name}/{entry.name}"
                    self._entries.append((share, mtime))

    def written_between(self, start: datetime, finish: datetime) -> list[str]:
        """The folders holding an MKV last written within [start, finish]."""
        folders = {
            str(PurePosixPath(path).parent)
            for path, mtime in self._entries
            if start <= mtime <= finish
        }
        return sorted(folders)


def locate(job: Manifest, video_root: Path, raw_index: RawIndex) -> Location:
    missing: list[str] = []
    completed = None
    if job.completed is not None:
        completed = job.completed.folder.path
        if not job.completed.folder.resolve(video_root).is_dir():
            missing.append(completed)
            completed = None
    raw: list[RawFolder] = []
    if job.raw is not None:
        path = job.raw.folder.path
        if job.raw.folder.resolve(video_root).is_dir():
            raw.append(RawFolder(path, RawFound.RECORDED))
        else:
            missing.append(path)
    elif job.start_time is not None and job.finish_time is not None:
        raw.extend(
            RawFolder(path, RawFound.WRITTEN_DURING_RUN)
            for path in raw_index.written_between(job.start_time, job.finish_time)
        )
    return Location(completed=completed, raw=tuple(raw), missing=tuple(missing))


def walk(video_root: Path, folder: str) -> Iterator[tuple[str, os.stat_result, bool]]:
    """Every entry under a folder, as (share path, stat, is a folder), in
    name order, not following links out of the share."""
    top = ShareRef(path=folder).resolve(video_root)
    for directory, folders, files in os.walk(top):
        folders.sort()
        relative = PurePosixPath(Path(directory).relative_to(top).as_posix())
        for name in folders:
            share = str(PurePosixPath(folder) / relative / name)
            yield share, os.stat(Path(directory) / name, follow_symlinks=False), True
        for name in sorted(files):
            share = str(PurePosixPath(folder) / relative / name)
            yield share, os.stat(Path(directory) / name, follow_symlinks=False), False
