"""The title structure of a DVD image or VIDEO_TS directory.

This is the identity check for an image whose `crc_id` no stamp carries.
pydvdid hashes file timestamps, and an image re-authored from a disc restamps
every file, so its CRC never matches the pressed disc's. The lengths and
chapter counts of its titles do. Each title's cells are what it plays, the
input to `segments`.

Lengths are in seconds of playback. An NTSC disc's IFO counts 30 frames to its
second while the video runs at 30000/1001, so what lsdvd prints is 0.1% short:
7.7 s on a two-hour title, more than the tolerances that compare an image with
MKVs ripped from it. Corrected, ffprobe's durations for those MKVs agree within
0.06 s, or exactly 0.5 s less where MakeMKV dropped a 0.5 s stub chapter.
"""

import ast
import re
from dataclasses import dataclass
from pathlib import Path

from reelbarrow.analysis.segments import Segment
from reelbarrow.analysis.tools import AnalysisError, run

# The IFO's frame rates, each with what its seconds are worth in playback.
SCALE = {25.0: 1.0, 29.97: 1001 / 1000}

# lsdvd's -Oy output, a Python literal in both the devenv's 0.17 and the image's
# 0.20, which differ only in quoting and commas. It is the only output with each
# cell's sectors. Its free text, the device path, the label and the IFO's IDs, is
# copied in unescaped, so those lines are lifted out before the literal is read:
# a quote in a file name or a label could otherwise end the string early.
_FREE_TEXT = re.compile(
    r"""^(\s*)'(device|title|vmg_id|provider_id|vts_id)' : (['"])(.*)\3(,?)$""",
    re.MULTILINE,
)


@dataclass(frozen=True, slots=True)
class DvdTitle:
    # The DVD's own title number, the one the stamp calls `disc_title`.
    disc_title: int
    # The title set holding it, which its cells' sectors count within.
    vts: int
    # As the IFO flags it: 29.97 or 25.
    fps: float
    duration: float
    # The length of each chapter, in order.
    chapters: tuple[float, ...]
    # What the title plays, cell by cell, as sectors of its title set.
    cells: tuple[Segment, ...]

    @property
    def chapter_starts(self) -> tuple[float, ...]:
        starts, elapsed = [], 0.0
        for length in self.chapters:
            starts.append(elapsed)
            elapsed += length
        return tuple(starts)


@dataclass(frozen=True, slots=True)
class DvdStructure:
    # The volume label of an image; None for a directory, which has none.
    label: str | None
    titles: tuple[DvdTitle, ...]


def dvd_structure(path: Path) -> DvdStructure:
    """List every title of an ISO, or of a directory holding VIDEO_TS/."""
    output = run(["lsdvd", "-c", "-d", "-v", "-Oy", str(path)])
    return parse_lsdvd(output.decode(errors="replace"))


def parse_lsdvd(output: str) -> DvdStructure:
    """Read `lsdvd -c -d -v -Oy`, as produced by dvd_structure() or a fixture."""
    free_text: dict[str, str] = {}

    def lift(line: re.Match[str]) -> str:
        free_text.setdefault(line[2], line[4])
        return f"{line[1]}'{line[2]}' : None{line[5]}"

    # libdvdread writes its warnings to stdout too, ahead of lsdvd's own.
    _, start, literal = _FREE_TEXT.sub(lift, output).partition("lsdvd = {")
    try:
        disc = ast.literal_eval(start[-1] + literal) if start else None
    except (SyntaxError, ValueError) as error:
        raise AnalysisError(f"lsdvd output not understood: {error}") from error
    if not isinstance(disc, dict) or "title" not in free_text:
        raise AnalysisError(f"lsdvd output not understood: {output[:200]!r}")

    # libdvdread's answer when there is no volume label to read.
    label = None if free_text["title"] == "unknown" else free_text["title"]
    return DvdStructure(label, tuple(_title(t) for t in disc.get("track", ())))


def _title(track: dict) -> DvdTitle:
    fps = float(track["fps"])
    if fps not in SCALE:
        raise AnalysisError(f"title {track['ix']} has frame rate {fps}")
    scale = SCALE[fps]
    vts = int(track["vts"])
    chapters = tuple(c["length"] * scale for c in track.get("chapter", ()))
    cells = tuple(
        Segment(vts, c["first_sector"], c["last_sector"] + 1, c["length"] * scale)
        for c in track.get("cell", ())
    )
    if len(chapters) and abs(sum(chapters) - track["length"] * scale) > 0.1:
        raise AnalysisError(
            f"title {track['ix']}'s chapters sum to {sum(chapters):.3f} s,"
            f" not its {track['length'] * scale:.3f} s"
        )
    return DvdTitle(
        disc_title=int(track["ix"]),
        vts=vts,
        fps=fps,
        duration=track["length"] * scale,
        chapters=chapters,
        cells=cells,
    )
