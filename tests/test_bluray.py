import hashlib
import shutil
import struct

import pytest

from reelbarrow.analysis.bluray import (
    TICKS,
    BlurayClip,
    BlurayPlaylist,
    bluray_clips,
    bluray_hashes,
    bluray_playlists,
    handbrake_duration,
    parse_clpi,
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
        ((0, 900 * TICKS), (1, 900 * TICKS), (1, 1500 * TICKS)),
    )
    assert playlist.duration == 2700.0
    assert playlist.item_starts == (0.0, 1200.0)
    assert playlist.chapter_starts == (0.0, 1200.0, 1800.0)


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


def clpi(*streams, video_type=1):
    """Clip information whose CPI holds an EP map: each stream as (PID, type,
    entry points in 45 kHz ticks). An entry point is split as the format does,
    bits 32-19 of its 90 kHz time in a coarse entry and 19-9 in a fine one."""
    entries, tables = b"", []
    for pid, kind, points in streams:
        coarse, fine = [], []
        for point in points:
            pts = 2 * point
            high = (pts >> 19) & 0x3FFF
            if not coarse or coarse[-1][1] != high:
                coarse.append((len(fine), high))
            fine.append((pts >> 9) & 0x7FF)
        table = struct.pack(">I", 4 + 8 * len(coarse))
        table += b"".join(
            struct.pack(">II", first << 14 | high, 0) for first, high in coarse
        )
        table += b"".join(struct.pack(">I", value << 17) for value in fine)
        tables.append((pid, kind, len(coarse), len(fine), table))
    offset = 2 + 12 * len(tables)
    body = b""
    for pid, kind, coarse_count, fine_count, table in tables:
        packed = kind << 34 | coarse_count << 18 | fine_count
        entries += struct.pack(">H", pid) + packed.to_bytes(6, "big")
        entries += struct.pack(">I", offset + len(body))
        body += table
    ep_map = bytes([0, len(tables)]) + entries + body
    cpi = struct.pack(">IH", 2 + len(ep_map), 1) + ep_map
    cpi_at = 40
    header = b"HDMV0200" + struct.pack(">IIIII", 0, 0, cpi_at, 0, 0)
    return header.ljust(cpi_at, b"\0") + cpi


# Entry points that cross coarse entries: 2**18 ticks apart in the coarse bits.
POINTS = (0, 256 * 10, 3 * 2**18 + 512, 2**20 + 256, 2**31 + 2**18)


def test_a_clips_entry_points():
    assert parse_clpi("00349", clpi((0x1011, 1, POINTS))) == BlurayClip("00349", POINTS)


def test_the_video_stream_is_read_whatever_comes_first():
    data = clpi((0x1100, 3, (0, 512)), (0x1011, 1, POINTS))
    assert parse_clpi("00349", data).entry_points == POINTS


def test_a_clip_without_a_cpi_has_no_entry_points():
    header = b"HDMV0200" + struct.pack(">IIIII", 0, 0, 40, 0, 0)
    data = header.ljust(40, b"\0") + struct.pack(">I", 0)
    assert parse_clpi("00001", data) == BlurayClip("00001", ())


def test_not_clip_information():
    with pytest.raises(AnalysisError, match="not clip information"):
        parse_clpi("00001", b"MPLS0200")


def test_truncated_clip_information():
    with pytest.raises(AnalysisError, match="not clip information this reads"):
        parse_clpi("00001", clpi((0x1011, 1, POINTS))[:60])


def test_every_clip_of_a_copy(disc):
    root = disc()
    (root / "BDMV/CLIPINF/00000.clpi").write_bytes(clpi((0x1011, 1, (0,))))
    assert list(bluray_clips(root)) == ["00000"]


def test_no_clips_is_refused(tmp_path):
    with pytest.raises(AnalysisError, match="CLIPINF"):
        bluray_clips(tmp_path)


# A featurette of 442 s on clip 00349 from 11.651 s, its keyframes about a
# second apart, and a 4.5 s clip of black after it, as on job 79.
START = int(11.651 * TICKS)
FEATURETTE = Segment("00349", START, START + 442 * TICKS, 442.0)
SPACER = Segment("00351", START, START + int(4.5 * TICKS), 4.5)
CLIPS = {
    "00349": BlurayClip("00349", tuple(START + k * TICKS for k in range(443))),
    "00351": BlurayClip("00351", (START, START + 2 * TICKS, START + int(3.9 * TICKS))),
}


def stub(at):
    """A chapter `at` seconds before the end of the spacer."""
    return (1, SPACER.end - int(at * TICKS))


def test_a_playlist_without_a_late_chapter_comes_out_whole():
    playlist = BlurayPlaylist("01223.mpls", (FEATURETTE,), ((0, START),))
    assert handbrake_duration(playlist, CLIPS) == 442.0


def test_a_stub_chapter_cuts_the_encode_at_the_keyframe_before_it():
    playlist = BlurayPlaylist(
        "01227.mpls", (FEATURETTE, SPACER), ((0, START), stub(0.25))
    )
    assert handbrake_duration(playlist, CLIPS) == pytest.approx(442 + 3.9, abs=1e-4)


def test_a_chapter_counts_as_late_within_a_second_and_a_half():
    late = BlurayPlaylist("x.mpls", (FEATURETTE, SPACER), ((0, START), stub(1.49)))
    on_time = BlurayPlaylist("x.mpls", (FEATURETTE, SPACER), ((0, START), stub(1.5)))
    assert handbrake_duration(late, CLIPS) == pytest.approx(442 + 2, abs=1e-4)
    assert handbrake_duration(on_time, CLIPS) == pytest.approx(446.5)


def test_a_mark_before_any_entry_point_cuts_at_its_item():
    clips = {**CLIPS, "00351": BlurayClip("00351", ())}
    playlist = BlurayPlaylist("x.mpls", (FEATURETTE, SPACER), ((0, START), stub(0.25)))
    assert handbrake_duration(playlist, clips) == pytest.approx(442.0)


def test_a_clip_without_its_information_is_refused():
    playlist = BlurayPlaylist("x.mpls", (FEATURETTE, SPACER), ((0, START), stub(0.25)))
    with pytest.raises(AnalysisError, match="no .clpi"):
        handbrake_duration(playlist, {"00349": CLIPS["00349"]})
