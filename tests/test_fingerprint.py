import json

import pytest

from reelbarrow.analysis.fingerprint import (
    Fingerprint,
    IncompleteFingerprint,
    check_complete,
    expected_frames,
    fingerprint,
)
from reelbarrow.analysis.tools import AnalysisError


def sound(seconds: float, frequency: int) -> tuple[str, ...]:
    """A tone over pink noise: distinct to fingerprint, where silence is not."""
    return (
        *("-f", "lavfi", "-i", f"sine=f={frequency}:d={seconds}"),
        *("-f", "lavfi", "-i", f"anoisesrc=d={seconds}:c=pink:a=0.3:seed={frequency}"),
    )


def mixed(inputs: int = 2, label: str = "a") -> tuple[str, ...]:
    return ("-filter_complex", f"amix=inputs={inputs}[{label}]", "-map", f"[{label}]")


def test_committed_fingerprints_are_complete(fixtures, fingerprints):
    sources = json.loads((fixtures / "fingerprints/sources.json").read_text())
    for name, source in sources.items():
        assert len(fingerprints[name].frames) == expected_frames(source["duration"])


@pytest.mark.parametrize(
    ("name", "captured_frames"),
    [
        # The lengths the design sessions' captures through kubectl exec came
        # back with: 154 s and 224 s short of their files.
        ("robinhood-140", 66830),
        ("rescuers-feature", 35584),
    ],
)
def test_the_truncated_captures_are_refused(fingerprints, name, captured_frames):
    complete = fingerprints[name]
    with pytest.raises(IncompleteFingerprint):
        check_complete(captured_frames, complete.duration)


def test_slack_is_a_couple_of_seconds(fingerprints):
    complete = fingerprints["robinhood-155"]
    frames = len(complete.frames)
    check_complete(frames - 16, complete.duration)
    with pytest.raises(IncompleteFingerprint):
        check_complete(frames - 17, complete.duration)
    with pytest.raises(IncompleteFingerprint):
        check_complete(frames + 17, complete.duration)


def test_text_round_trips(fingerprints):
    complete = fingerprints["rescuers-title71"]
    again = Fingerprint.from_text(complete.to_text(), complete.duration)
    assert again == complete


def test_fingerprint_of_a_file(ffmpeg):
    path = ffmpeg("whole.mkv", *sound(60, 440), *mixed(), "-c:a", "libopus")
    result = fingerprint(path)
    assert result.duration == pytest.approx(60, abs=0.05)
    assert len(result.frames) == expected_frames(result.duration)


def test_a_truncated_file_is_refused(ffmpeg, tmp_path):
    whole = ffmpeg("whole.mkv", *sound(60, 440), *mixed(), "-c:a", "libopus")
    # Cut short the way a copy that stopped part way would be: the header
    # still claims the full 60 s.
    truncated = tmp_path / "truncated.mkv"
    data = whole.read_bytes()
    truncated.write_bytes(data[: len(data) // 2])
    with pytest.raises(IncompleteFingerprint):
        fingerprint(truncated)


def test_the_first_audio_track_is_the_one_fingerprinted(ffmpeg):
    first = ffmpeg("first.mka", *sound(20, 440), *mixed(), "-c:a", "flac")
    # The first track again, beside a six-channel track marked as the default,
    # which is the one libavformat would rank best.
    both = ffmpeg(
        "both.mka",
        *("-i", str(first)),
        *sound(20, 880),
        *("-filter_complex", "[1][2]amix=inputs=2[b]"),
        *("-map", "0:a", "-map", "[b]", "-c:a", "flac", "-ac:a:1", "6"),
        *("-disposition:a:0", "0", "-disposition:a:1", "default"),
    )
    assert fingerprint(both).frames == fingerprint(first).frames


def test_a_file_without_audio_fails(ffmpeg):
    video = ffmpeg(
        "video.mkv", "-f", "lavfi", "-i", "testsrc=d=3:s=64x48:r=10", "-c:v", "ffv1"
    )
    with pytest.raises(AnalysisError, match="no audio"):
        fingerprint(video)
