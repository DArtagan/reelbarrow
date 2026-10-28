import hashlib
import shutil
import struct

import pytest

from reelbarrow.analysis.bluray import (
    TICKS,
    BlurayPlaylist,
    bluray_hashes,
    bluray_playlists,
    parse_mpls,
)
from reelbarrow.analysis.segments import Segment
from reelbarrow.analysis.tools import AnalysisError

DISC = {
    "BDMV/index.bdmv": b"INDX0200 index",
    "BDMV/MovieObject.bdmv": b"MOBJ0200 objects",
    "BDMV/PLAYLIST/00000.mpls": b"MPLS0200 feature",
    "BDMV/PLAYLIST/00001.mpls": b"MPLS0200 trailer",
    "BDMV/CLIPINF/00000.clpi": b"HDMV0200 clip",
    "BDMV/STREAM/00000.m2ts": b"\x47" * 6144,
    "BDMV/STREAM/00001.m2ts": b"\x47" * 1536,
    "BDMV/BACKUP/index.bdmv": b"INDX0200 index",
    "CERTIFICATE/id.bdmv": b"shared by unrelated discs",
}


@pytest.fixture
def disc(tmp_path):
    def make(name="disc", files=DISC):
        root = tmp_path / name
        for relative, data in files.items():
            (root / relative).parent.mkdir(parents=True, exist_ok=True)
            (root / relative).write_bytes(data)
        return root

    return make


def test_the_hashes_are_as_specified(disc):
    hashes = bluray_hashes(disc())

    nav = hashlib.sha1()
    for relative in (
        "BDMV/MovieObject.bdmv",
        "BDMV/index.bdmv",
        "BDMV/PLAYLIST/00000.mpls",
        "BDMV/PLAYLIST/00001.mpls",
    ):
        nav.update(relative.encode() + DISC[relative])
    listing = [
        "BDMV/MovieObject.bdmv:16",
        "BDMV/index.bdmv:14",
        "BDMV/BACKUP/index.bdmv:14",
        "BDMV/CLIPINF/00000.clpi:13",
        "BDMV/PLAYLIST/00000.mpls:16",
        "BDMV/PLAYLIST/00001.mpls:16",
        "BDMV/STREAM/00000.m2ts:6144",
        "BDMV/STREAM/00001.m2ts:1536",
    ]

    assert hashes.nav == nav.hexdigest()
    assert hashes.completeness == hashlib.sha1("\n".join(listing).encode()).hexdigest()
    assert (hashes.files, hashes.bytes) == (8, 7769)


def test_a_partial_copy_keeps_its_identity(disc):
    complete = bluray_hashes(disc("complete"))
    partial_files = {k: v for k, v in DISC.items() if k != "BDMV/STREAM/00000.m2ts"}
    partial = bluray_hashes(disc("partial", partial_files))

    assert partial.nav == complete.nav
    assert partial.completeness != complete.completeness


def test_id_bdmv_is_no_part_of_either_hash(disc):
    one = bluray_hashes(disc("one"))
    other = disc("other")
    (other / "CERTIFICATE/id.bdmv").write_bytes(b"different")
    assert bluray_hashes(other) == one
    shutil.rmtree(other / "CERTIFICATE")
    assert bluray_hashes(other) == one


def test_a_different_playlist_is_a_different_disc(disc):
    one = bluray_hashes(disc("one"))
    other = disc("other")
    (other / "BDMV/PLAYLIST/00001.mpls").write_bytes(b"MPLS0200 another")
    assert bluray_hashes(other).nav != one.nav


def test_no_bdmv_is_refused(tmp_path):
    with pytest.raises(AnalysisError, match="BDMV"):
        bluray_hashes(tmp_path)


def mpls(items, marks, angles=0):
    """A playlist in the MPLS layout: items as (clip, in, out) in ticks, marks
    as (type, item, time). `angles` pads each item as a multi-angle one is, so
    the reader has to step by the item's length."""
    body = b""
    for clip, start, end in items:
        item = (
            clip.encode()
            + b"M2TS"
            + b"\x00\x00"
            + b"\x00"
            + struct.pack(">II", start, end)
        )
        item += b"\x00" * (16 + 10 * angles)
        body += struct.pack(">H", len(item)) + item
    playlist = struct.pack(">IHHH", 6 + len(body), 0, len(items), 0) + body
    mark_list = b"".join(
        struct.pack(">xBHIHI", kind, item, time, 0x1011, 0)
        for kind, item, time in marks
    )
    mark_section = struct.pack(">IH", 2 + len(mark_list), len(marks)) + mark_list
    # An AppInfoPlayList, unread, sits between the header and the playlist.
    app_info = struct.pack(">I", 14) + b"\x00" * 14
    items_at = 40 + len(app_info)
    marks_at = items_at + len(playlist)
    header = b"MPLS0200" + struct.pack(">III", items_at, marks_at, 0) + b"\x00" * 20
    return header + app_info + playlist + mark_section


# A play-all of two episodes, each its own clip, with a chapter at each
# episode's start and one inside the second, and a link point that is no chapter.
PLAY_ALL = mpls(
    [("00001", 900 * TICKS, 2100 * TICKS), ("00002", 900 * TICKS, 2400 * TICKS)],
    [
        (1, 0, 900 * TICKS),
        (1, 1, 900 * TICKS),
        (2, 1, 1000 * TICKS),
        (1, 1, 1500 * TICKS),
    ],
)


def test_a_playlist_is_its_clips_in_order():
    playlist = parse_mpls("00800.mpls", PLAY_ALL)
    assert playlist == BlurayPlaylist(
        "00800.mpls",
        (
            Segment("00001", 900 * TICKS, 2100 * TICKS, 1200.0),
            Segment("00002", 900 * TICKS, 2400 * TICKS, 1500.0),
        ),
        (0.0, 1200.0, 1800.0),
    )
    assert playlist.duration == 2700.0


def test_a_long_item_is_stepped_over_by_its_length():
    playlist = parse_mpls(
        "00001.mpls", mpls([("00001", 0, TICKS), ("00002", 0, 2 * TICKS)], [], angles=3)
    )
    assert [item.source for item in playlist.items] == ["00001", "00002"]
    assert playlist.chapter_starts == ()


def test_a_mark_past_the_last_item_is_dropped():
    playlist = parse_mpls(
        "00001.mpls", mpls([("00001", 0, TICKS)], [(1, 0, 0), (1, 5, 0)])
    )
    assert playlist.chapter_starts == (0.0,)


def test_not_a_playlist():
    with pytest.raises(AnalysisError, match="not a playlist"):
        parse_mpls("index.bdmv", b"INDX0200 index")


def test_a_truncated_playlist():
    with pytest.raises(AnalysisError, match="not a playlist this reads"):
        parse_mpls("00800.mpls", PLAY_ALL[:60])


def test_every_playlist_of_a_copy(disc):
    root = disc()
    (root / "BDMV/PLAYLIST/00000.mpls").write_bytes(PLAY_ALL)
    (root / "BDMV/PLAYLIST/00001.mpls").write_bytes(mpls([("00001", 0, TICKS)], []))
    (root / "BDMV/PLAYLIST/notes.txt").write_bytes(b"not a playlist")
    assert [p.playlist for p in bluray_playlists(root)] == ["00000.mpls", "00001.mpls"]


def test_no_playlists_is_refused(tmp_path):
    with pytest.raises(AnalysisError, match="PLAYLIST"):
        bluray_playlists(tmp_path)
