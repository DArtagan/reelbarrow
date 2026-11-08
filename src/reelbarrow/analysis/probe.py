import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from reelbarrow.analysis.tools import AnalysisError, run


@dataclass(frozen=True, slots=True)
class Stream:
    index: int
    codec_type: str
    codec_name: str | None
    # Seconds, or None when neither the stream nor its tags give one.
    duration: float | None
    channels: int | None
    language: str | None
    title: str | None


@dataclass(frozen=True, slots=True)
class Chapter:
    start: float
    end: float
    title: str | None


@dataclass(frozen=True, slots=True)
class Probe:
    format_name: str
    duration: float | None
    size: int | None
    tags: dict[str, str]
    streams: tuple[Stream, ...]
    chapters: tuple[Chapter, ...]
    # ffprobe's own output, kept whole because it becomes a fixture.
    raw: dict[str, Any]

    def of_type(self, codec_type: str) -> tuple[Stream, ...]:
        return tuple(s for s in self.streams if s.codec_type == codec_type)


def probe(path: Path) -> Probe:
    output = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-show_chapters",
            "-of",
            "json",
            str(path),
        ]
    )
    return parse_probe(json.loads(output))


def parse_probe(raw: dict[str, Any]) -> Probe:
    """Read ffprobe's JSON, as produced by probe() or loaded from a fixture."""
    if "format" not in raw:
        raise AnalysisError("ffprobe output has no format section")
    fmt = raw["format"]
    return Probe(
        format_name=fmt["format_name"],
        duration=_seconds(fmt.get("duration")),
        size=int(fmt["size"]) if "size" in fmt else None,
        tags=dict(fmt.get("tags", {})),
        streams=tuple(_stream(s) for s in raw.get("streams", ())),
        chapters=tuple(
            Chapter(
                start=float(c["start_time"]),
                end=float(c["end_time"]),
                title=c.get("tags", {}).get("title"),
            )
            for c in raw.get("chapters", ())
        ),
        raw=raw,
    )


def _stream(raw: dict[str, Any]) -> Stream:
    tags = raw.get("tags", {})
    duration = _seconds(raw.get("duration"))
    if duration is None:
        # Matroska carries per-stream durations only as a tag, written by the
        # muxer as HH:MM:SS.nnnnnnnnn; ARM's transcodes have no other.
        tag = next((v for k, v in tags.items() if k.upper() == "DURATION"), None)
        duration = _clock(tag) if tag else None
    return Stream(
        index=int(raw["index"]),
        codec_type=raw.get("codec_type", "unknown"),
        codec_name=raw.get("codec_name"),
        duration=duration,
        channels=int(raw["channels"]) if "channels" in raw else None,
        language=tags.get("language"),
        title=tags.get("title"),
    )


def _seconds(value: str | None) -> float | None:
    if value is None or value == "N/A":
        return None
    return float(value)


def _clock(value: str) -> float:
    hours, minutes, seconds = value.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
