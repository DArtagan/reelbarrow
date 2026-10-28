import hashlib
import os
import struct
from dataclasses import dataclass
from pathlib import Path

from reelbarrow.analysis.segments import Segment
from reelbarrow.analysis.tools import AnalysisError

# The navigation files: equal across every backup of one disc, complete or not.
# CERTIFICATE/id.bdmv is deliberately absent. It sits outside BDMV/, and three
# different Dark Knight bonus discs share one.
NAV_FILES = ("BDMV/index.bdmv", "BDMV/MovieObject.bdmv")
NAV_DIR = "BDMV/PLAYLIST/"


@dataclass(frozen=True, slots=True)
class BlurayHashes:
    # SHA-1 over the path and bytes of each navigation file: the disc's identity.
    nav: str
    # SHA-1 over the path and size of every file under BDMV/: equal only for
    # copies holding the same files.
    completeness: str
    files: int
    bytes: int


def bluray_hashes(root: Path) -> BlurayHashes:
    """Hash a raw Blu-ray copy, given the directory that holds its BDMV/."""
    if not (root / "BDMV").is_dir():
        raise AnalysisError(f"{root} has no BDMV directory")

    nav = hashlib.sha1()
    entries = []
    total = 0
    # Directories in sorted order, each one's files before its subdirectories,
    # so the hashes do not depend on the order the filesystem lists them in.
    for dirpath, dirnames, filenames in os.walk(root / "BDMV"):
        dirnames.sort()
        for name in sorted(filenames):
            path = Path(dirpath, name)
            relative = path.relative_to(root).as_posix()
            size = path.stat().st_size
            entries.append(f"{relative}:{size}")
            total += size
            if relative in NAV_FILES or relative.startswith(NAV_DIR):
                nav.update(os.fsencode(relative))
                nav.update(path.read_bytes())

    completeness = hashlib.sha1(os.fsencode("\n".join(entries))).hexdigest()
    return BlurayHashes(nav.hexdigest(), completeness, len(entries), total)


# A clip's times count a 45 kHz clock.
TICKS = 45000
# A playlist mark of this type is a chapter; type 2 is a link point.
_ENTRY_MARK = 1


@dataclass(frozen=True, slots=True)
class BlurayPlaylist:
    # Its file name in BDMV/PLAYLIST/, as the stamp's `playlist` gives it.
    playlist: str
    # Each play item's clip between its in and out times, in play order.
    items: tuple[Segment, ...]
    # Where each chapter begins, in seconds from the start of the playlist.
    chapter_starts: tuple[float, ...]

    @property
    def duration(self) -> float:
        return sum(item.seconds for item in self.items)


def bluray_playlists(root: Path) -> tuple[BlurayPlaylist, ...]:
    """Read every playlist of a raw Blu-ray copy, given the directory holding BDMV/."""
    folder = root / "BDMV" / "PLAYLIST"
    if not folder.is_dir():
        raise AnalysisError(f"{root} has no BDMV/PLAYLIST directory")
    return tuple(
        parse_mpls(path.name, path.read_bytes())
        for path in sorted(folder.iterdir())
        if path.suffix.lower() == ".mpls"
    )


def parse_mpls(name: str, data: bytes) -> BlurayPlaylist:
    """Read one playlist's play items and chapter marks.

    Only the first angle of a multi-angle item is read, the one a player starts
    on. Sub-paths, which carry secondary audio and video, are not.
    """
    if data[:4] != b"MPLS":
        raise AnalysisError(f"{name} is not a playlist")
    try:
        items_at, marks_at = struct.unpack_from(">II", data, 8)
        (count,) = struct.unpack_from(">H", data, items_at + 6)
        offset = items_at + 10
        items, starts, elapsed = [], [], 0.0
        for _ in range(count):
            (length,) = struct.unpack_from(">H", data, offset)
            clip = data[offset + 2 : offset + 7].decode("ascii")
            start, end = struct.unpack_from(">II", data, offset + 14)
            items.append(Segment(clip, start, end, (end - start) / TICKS))
            starts.append(elapsed)
            elapsed += (end - start) / TICKS
            offset += 2 + length

        chapters = []
        (marks,) = struct.unpack_from(">H", data, marks_at + 4)
        for mark in range(marks):
            kind, item, stamp = struct.unpack_from(
                ">xBHI", data, marks_at + 6 + 14 * mark
            )
            if kind == _ENTRY_MARK and item < len(items):
                chapters.append(starts[item] + (stamp - items[item].start) / TICKS)
    except (struct.error, UnicodeDecodeError) as error:
        raise AnalysisError(f"{name} is not a playlist this reads: {error}") from error
    return BlurayPlaylist(name, tuple(items), tuple(chapters))
