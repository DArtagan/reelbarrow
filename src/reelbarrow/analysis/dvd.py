"""The title structure of a DVD image or VIDEO_TS directory.

This is the identity check for images. pydvdid hashes file timestamps, and an
image re-authored from a disc restamps every file, so its CRC never matches
the pressed disc's. The lengths and chapter counts of its titles do.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from reelbarrow.analysis.tools import AnalysisError, run

# lsdvd's plain output, which is the same in the devenv's 0.17 and the image's
# 0.20. Its XML output copies the disc's free-text fields unescaped.
_DISC_TITLE = re.compile(r"^Disc Title: (.*)$", re.MULTILINE)
_TITLE = re.compile(
    r"^Title: (\d+), Length: (\d+):(\d+):([\d.]+) Chapters: (\d+),", re.MULTILINE
)
_CHAPTER = re.compile(r"^\tChapter: (\d+), Length: (\d+):(\d+):([\d.]+),")


@dataclass(frozen=True, slots=True)
class DvdTitle:
    number: int
    duration: float
    # The length of each chapter, in order.
    chapters: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class DvdStructure:
    # The volume label of an image; None for a directory, which has none.
    label: str | None
    titles: tuple[DvdTitle, ...]


def dvd_structure(path: Path) -> DvdStructure:
    """List every title of an ISO, or of a directory holding VIDEO_TS/."""
    return parse_lsdvd(run(["lsdvd", "-c", str(path)]).decode(errors="replace"))


def parse_lsdvd(output: str) -> DvdStructure:
    label_match = _DISC_TITLE.search(output)
    if label_match is None:
        raise AnalysisError("lsdvd output has no disc title")
    # libdvdread's answer when there is no volume label to read.
    label = None if label_match[1] == "unknown" else label_match[1]

    titles = []
    for block in re.split(r"^(?=Title: )", output, flags=re.MULTILINE)[1:]:
        title = _TITLE.match(block)
        if title is None:
            raise AnalysisError(f"lsdvd title line not understood: {block!r}")
        chapters = tuple(
            _clock(*m.groups()[1:])
            for m in map(_CHAPTER.match, block.splitlines()[1:])
            if m
        )
        if len(chapters) != int(title[5]):
            raise AnalysisError(
                f"lsdvd listed {len(chapters)} chapters for title {title[1]},"
                f" which claims {title[5]}"
            )
        titles.append(DvdTitle(int(title[1]), _clock(*title.groups()[1:4]), chapters))
    return DvdStructure(label, tuple(titles))


def _clock(hours: str, minutes: str, seconds: str) -> float:
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
