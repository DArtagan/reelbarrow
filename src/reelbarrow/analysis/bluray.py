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
    # Each chapter's mark: the play item it falls in, and its time on that
    # item's clip.
    chapter_marks: tuple[tuple[int, int], ...]

    @property
    def duration(self) -> float:
        return sum(item.seconds for item in self.items)

    @property
    def item_starts(self) -> tuple[float, ...]:
        """Where each play item begins, in seconds from the start of the playlist."""
        starts, elapsed = [], 0.0
        for item in self.items:
            starts.append(elapsed)
            elapsed += item.seconds
        return tuple(starts)

    @property
    def chapter_starts(self) -> tuple[float, ...]:
        """Where each chapter begins, in seconds from the start of the playlist."""
        starts = self.item_starts
        return tuple(
            starts[item] + (stamp - self.items[item].start) / TICKS
            for item, stamp in self.chapter_marks
        )


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
        items = []
        for _ in range(count):
            (length,) = struct.unpack_from(">H", data, offset)
            clip = data[offset + 2 : offset + 7].decode("ascii")
            start, end = struct.unpack_from(">II", data, offset + 14)
            items.append(Segment(clip, start, end, (end - start) / TICKS))
            offset += 2 + length

        marks = []
        (count,) = struct.unpack_from(">H", data, marks_at + 4)
        for mark in range(count):
            kind, item, stamp = struct.unpack_from(
                ">xBHI", data, marks_at + 6 + 14 * mark
            )
            if kind == _ENTRY_MARK and item < len(items):
                marks.append((item, stamp))
    except (struct.error, UnicodeDecodeError) as error:
        raise AnalysisError(f"{name} is not a playlist this reads: {error}") from error
    return BlurayPlaylist(name, tuple(items), tuple(marks))


# An EP_map entry's stream type for video.
_EP_VIDEO = 1


@dataclass(frozen=True, slots=True)
class BlurayClip:
    # Its number, which names its files in BDMV/CLIPINF/ and BDMV/STREAM/ and a
    # play item's clip.
    clip: str
    # Where its video can be entered: each I-picture's time on the clip's 45 kHz
    # clock, rounded down to 256 ticks as the EP map stores it. libbluray finds a
    # mark at the last of these at or before it, from the same rounded values.
    entry_points: tuple[int, ...]


def bluray_clips(root: Path) -> dict[str, BlurayClip]:
    """Read every clip's entry points, given the directory holding BDMV/."""
    folder = root / "BDMV" / "CLIPINF"
    if not folder.is_dir():
        raise AnalysisError(f"{root} has no BDMV/CLIPINF directory")
    clips = (
        parse_clpi(path.stem, path.read_bytes())
        for path in sorted(folder.iterdir())
        if path.suffix.lower() == ".clpi"
    )
    return {clip.clip: clip for clip in clips}


def parse_clpi(clip: str, data: bytes) -> BlurayClip:
    """Read a clip's entry points from the EP map in its CPI.

    Each entry splits an I-picture's time between a coarse table and a fine
    one, the bit they share kept in the fine, as libbluray reassembles them.
    """
    if data[:4] != b"HDMV":
        raise AnalysisError(f"{clip}.clpi is not clip information")
    try:
        (cpi,) = struct.unpack_from(">I", data, 16)
        (length,) = struct.unpack_from(">I", data, cpi)
        if length == 0:
            return BlurayClip(clip, ())
        ep_map = cpi + 6
        for stream in range(data[ep_map + 1]):
            entry = ep_map + 2 + 12 * stream
            packed = int.from_bytes(data[entry + 2 : entry + 8], "big")
            if (packed >> 34) & 0xF != _EP_VIDEO:
                continue
            coarse_count, fine_count = (packed >> 18) & 0xFFFF, packed & 0x3FFFF
            (table,) = struct.unpack_from(">I", data, entry + 8)
            return BlurayClip(
                clip, _entry_points(data, ep_map + table, coarse_count, fine_count)
            )
    except (struct.error, IndexError) as error:
        raise AnalysisError(
            f"{clip}.clpi is not clip information this reads: {error}"
        ) from error
    return BlurayClip(clip, ())


def _entry_points(
    data: bytes, table: int, coarse_count: int, fine_count: int
) -> tuple[int, ...]:
    (fine_at,) = struct.unpack_from(">I", data, table)
    coarse = [
        struct.unpack_from(">I", data, table + 4 + 8 * i)[0]
        for i in range(coarse_count)
    ]
    # Each coarse entry gives its first fine entry's index and the high bits.
    firsts = [word >> 14 for word in coarse] + [fine_count]
    points = []
    for i, word in enumerate(coarse):
        high = (word & 0x3FFF & ~1) << 18
        for f in range(firsts[i], firsts[i + 1]):
            (fine,) = struct.unpack_from(">I", data, table + fine_at + 4 * f)
            points.append(high + (((fine >> 17) & 0x7FF) << 8))
    return tuple(points)


# HandBrake drops a chapter that starts within this many seconds of a title's
# end (libhb/bd.c, 1.10 and 1.11).
HANDBRAKE_CHAPTER_MARGIN = 1.5


def handbrake_duration(playlist: BlurayPlaylist, clips: dict[str, BlurayClip]) -> float:
    """The length HandBrake's transcode of a playlist comes out at, in seconds.

    The playlist's own, unless a chapter starts within 1.5 s of its end. HandBrake
    drops that chapter, and its reader ends the encode when playback reaches it,
    which libbluray does at the clip's last entry point at or before the mark. On
    22 transcodes this is within two frames of the file (E35); a tolerance on the
    playlist's length is up to a second wrong.
    """
    duration, starts = playlist.duration, playlist.item_starts
    for (item, stamp), start in zip(
        playlist.chapter_marks, playlist.chapter_starts, strict=True
    ):
        if duration - start >= HANDBRAKE_CHAPTER_MARGIN:
            continue
        segment = playlist.items[item]
        if segment.source not in clips:
            raise AnalysisError(
                f"{playlist.playlist} plays clip {segment.source}, which has no .clpi"
            )
        before = [
            p for p in clips[segment.source].entry_points if segment.start <= p <= stamp
        ]
        point = max(before, default=segment.start)
        return starts[item] + (point - segment.start) / TICKS
    return duration
