import pytest

from reelbarrow.analysis import video
from reelbarrow.analysis.tools import AnalysisError

PATTERN = ("-f", "lavfi", "-i", "testsrc=d=3:s=64x48:r=10", "-c:v", "ffv1")


def test_same_video_in_different_files_hashes_equal(ffmpeg):
    plain = ffmpeg("plain.mkv", *PATTERN)
    # The same video stream, copied beside an audio track and a title.
    remuxed = ffmpeg(
        "remuxed.mkv",
        *("-i", str(plain), "-f", "lavfi", "-i", "sine=d=3"),
        *("-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "flac"),
        *("-metadata", "title=Something else"),
    )
    assert video.md5(plain) == video.md5(remuxed)


def test_cover_art_does_not_change_the_hash(ffmpeg):
    plain = ffmpeg("plain.mkv", *PATTERN)
    cover = ffmpeg(
        "cover.png", "-f", "lavfi", "-i", "color=red:s=32x32", "-frames:v", "1"
    )
    covered = ffmpeg(
        "covered.mkv",
        *("-i", str(plain), "-c", "copy"),
        *("-attach", str(cover), "-metadata:s:t", "mimetype=image/png"),
    )
    assert video.md5(plain) == video.md5(covered)


def test_different_video_hashes_differ(ffmpeg):
    one = ffmpeg("one.mkv", *PATTERN)
    other = ffmpeg(
        "other.mkv", "-f", "lavfi", "-i", "testsrc2=d=3:s=64x48:r=10", "-c:v", "ffv1"
    )
    assert video.md5(one) != video.md5(other)


def test_a_file_without_video_fails(ffmpeg):
    audio = ffmpeg("audio.mka", "-f", "lavfi", "-i", "sine=d=3", "-c:a", "flac")
    with pytest.raises(AnalysisError):
        video.md5(audio)
