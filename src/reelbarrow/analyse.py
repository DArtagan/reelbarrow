"""`reelbarrow analyse`: the files a manifest's unit of work holds, measured.

The document is what the planner reads, from the share or from a fixture
(*Testing*, layer 1, in the design), so a fixture is this command's output,
captured where the media is. It holds only what a rule reads: each file's size
and modification time, which a plan's basis records; a video's length and
chapter starts, which identify the feature and pair it with its raw source;
and, for a completed folder's videos, each subtitle track's flags and events,
which tell a full track wrongly forced from a forced-only one.
Each new rule that reads more adds a field here, and the case that needs it
captures it. It identifies nothing and plans nothing, and writes no files.
"""

import os
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from reelbarrow import intake
from reelbarrow.analysis.probe import probe, subtitle_events
from reelbarrow.analysis.tools import AnalysisError
from reelbarrow.intake import RawFound, RawIndex
from reelbarrow.manifest import Manifest, ShareRef

SCHEMA = 1
# Probed for length and chapters; nothing else on the share is a video ARM
# makes or keeps.
VIDEO_SUFFIXES = frozenset({".mkv", ".mp4", ".m4v"})


class Model(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class Subtitle(Model):
    codec: str | None
    language: str | None
    default: bool
    forced: bool
    events: int = Field(description="Lines of text or pictures put on screen.")


class Video(Model):
    duration: float = Field(description="Seconds, the container's.")
    chapters: list[float] = Field(
        description="Each chapter's start, in seconds. Empty: none listed."
    )
    subtitles: list[Subtitle] | None = Field(
        default=None,
        description="Each subtitle track, in the file's order. Null: not "
        "counted, as a raw copy's aren't: counting reads the whole file, and "
        "only a transcode's flags are edited.",
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


def measure(video_root: Path, path: str, *, subtitles: bool = False) -> Folder:
    """A folder and everything under it; with `subtitles`, each video's
    subtitle tracks counted too."""
    resolved = ShareRef(path=path).resolve(video_root)
    folders: list[Entry] = []
    files: list[File] = []
    for share, stat, is_folder in intake.walk(video_root, path):
        if is_folder:
            folders.append(Entry(path=share, mtime=_time(stat.st_mtime)))
        else:
            files.append(_file(video_root, share, stat, subtitles))
    return Folder(
        path=path,
        mtime=_time(resolved.stat().st_mtime),
        folders=folders,
        files=files,
    )


def _file(video_root: Path, path: str, stat: os.stat_result, subtitles: bool) -> File:
    file = File(path=path, mtime=_time(stat.st_mtime), size=stat.st_size)
    if not file.is_video:
        return file
    resolved = ShareRef(path=path).resolve(video_root)
    try:
        measured = probe(resolved)
        events = subtitle_events(resolved) if subtitles else None
    except (AnalysisError, ValueError) as error:
        return file.model_copy(update={"error": str(error)})
    if measured.duration is None:
        return file.model_copy(update={"error": "ffprobe gives no duration"})
    tracks = measured.of_type("subtitle")
    if events is not None and len(events) != len(tracks):
        return file.model_copy(
            update={
                "error": f"{len(tracks)} subtitle tracks, but events counted "
                f"for {len(events)}"
            }
        )
    video = Video(
        duration=measured.duration,
        chapters=[chapter.start for chapter in measured.chapters],
        subtitles=None
        if events is None
        else [
            Subtitle(
                codec=track.codec_name,
                language=track.language,
                default=track.default,
                forced=track.forced,
                events=count,
            )
            for track, count in zip(tracks, events, strict=True)
        ],
    )
    return file.model_copy(update={"video": video})


def analyse(job: Manifest, video_root: Path, raw_index: RawIndex) -> Analysis:
    location = intake.locate(job, video_root, raw_index)
    completed = None
    if location.completed is not None:
        completed = measure(video_root, location.completed, subtitles=True)
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
