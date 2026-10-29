import pytest

from reelbarrow.analysis.tools import AnalysisError
from reelbarrow.analysis.video import video_md5

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
    assert video_md5(plain) == video_md5(remuxed)


def test_different_video_hashes_differ(ffmpeg):
    one = ffmpeg("one.mkv", *PATTERN)
    other = ffmpeg(
        "other.mkv", "-f", "lavfi", "-i", "testsrc2=d=3:s=64x48:r=10", "-c:v", "ffv1"
    )
    assert video_md5(one) != video_md5(other)


def test_a_file_without_video_fails(ffmpeg):
    audio = ffmpeg("audio.mka", "-f", "lavfi", "-i", "sine=d=3", "-c:a", "flac")
    with pytest.raises(AnalysisError):
        video_md5(audio)
