"""`reelbarrow analyse`: the files a manifest's unit of work holds, measured.

The document is what the planner reads, from the share or from a fixture
(*Testing*, layer 1, in the design), so a fixture is this command's output,
captured where the media is. It holds only what a rule reads: each file's size
and modification time, which a plan's basis records, and a video's length and
chapter starts, which identify the feature and pair it with its raw source.
Each new rule that reads more adds a field here, and the case that needs it
captures it. It identifies nothing and plans nothing, and writes no files.
"""

import os
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from reelbarrow import intake
from reelbarrow.analysis.probe import probe
from reelbarrow.analysis.tools import AnalysisError
from reelbarrow.intake import RawFound, RawIndex
from reelbarrow.manifest import Manifest, ShareRef

SCHEMA = 1
# Probed for length and chapters; nothing else on the share is a video ARM
# makes or keeps.
VIDEO_SUFFIXES = frozenset({".mkv", ".mp4", ".m4v"})


class Model(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class Video(Model):
    duration: float = Field(description="Seconds, the container's.")
    chapters: list[float] = Field(
        description="Each chapter's start, in seconds. Empty: none listed."
    )


class Entry(Model):
    path: str = Field(description="From the share's root, as a manifest's.")
    mtime: AwareDatetime


class File(Entry):
    size: int
    video: Video | None = Field(
        default=None, description="A video file's measurements. Null: not a video."
    )
    error: str | None = Field(
        default=None, description="Why a video couldn't be measured."
    )

    @property
    def name(self) -> str:
        return PurePosixPath(self.path).name

    @property
    def is_video(self) -> bool:
        return PurePosixPath(self.path).suffix.lower() in VIDEO_SUFFIXES


class Folder(Entry):
    folders: list[Entry] = Field(description="Every folder under it, at any depth.")
    files: list[File] = Field(description="Every file under it, at any depth.")


class RawFolder(Folder):
    found: RawFound


class Analysis(Model):
    schema_: Literal[1] = Field(alias="schema")
    source: str
    id: str
    completed: Folder | None = Field(
        description="The completed folder. Null: none recorded, or not there."
    )
    raw: list[RawFolder] = Field(description="Each raw folder intake found.")
    missing: list[str] = Field(
        description="Paths the manifest records that aren't on the share."
    )

    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)

    def to_json(self) -> dict:
        return self.model_dump(mode="json", by_alias=True)


def _time(seconds: float) -> datetime:
    return datetime.fromtimestamp(seconds, UTC)


def measure(video_root: Path, path: str) -> Folder:
    """A folder and everything under it."""
    resolved = ShareRef(path=path).resolve(video_root)
    folders: list[Entry] = []
    files: list[File] = []
    for share, stat, is_folder in intake.walk(video_root, path):
        if is_folder:
            folders.append(Entry(path=share, mtime=_time(stat.st_mtime)))
        else:
            files.append(_file(video_root, share, stat))
    return Folder(
        path=path,
        mtime=_time(resolved.stat().st_mtime),
        folders=folders,
        files=files,
    )


def _file(video_root: Path, path: str, stat: os.stat_result) -> File:
    file = File(path=path, mtime=_time(stat.st_mtime), size=stat.st_size)
    if not file.is_video:
        return file
    try:
        measured = probe(ShareRef(path=path).resolve(video_root))
    except (AnalysisError, ValueError) as error:
        return file.model_copy(update={"error": str(error)})
    if measured.duration is None:
        return file.model_copy(update={"error": "ffprobe gives no duration"})
    video = Video(
        duration=measured.duration,
        chapters=[chapter.start for chapter in measured.chapters],
    )
    return file.model_copy(update={"video": video})


def analyse(job: Manifest, video_root: Path, raw_index: RawIndex) -> Analysis:
    location = intake.locate(job, video_root, raw_index)
    completed = None
    if location.completed is not None:
        completed = measure(video_root, location.completed)
    raw = []
    for folder in location.raw:
        measured = measure(video_root, folder.path)
        raw.append(RawFolder(**dict(measured), found=folder.found))
    return Analysis(
        schema=SCHEMA,
        source=job.source,
        id=job.id,
        completed=completed,
        raw=raw,
        missing=list(location.missing),
    )
