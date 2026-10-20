import hashlib
import shutil

import pytest

from reelbarrow.analysis.bluray import bluray_hashes
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
