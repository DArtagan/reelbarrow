import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from reelbarrow.analysis.probe import Probe, probe
from reelbarrow.analysis.tools import AnalysisError

SAMPLE_RATE = 11025
# Chromaprint's analysis frame is 4096 samples, advanced 1365 at a time.
FRAME_SAMPLES = 4096
FRAME_STEP = 1365
FRAME_SECONDS = FRAME_STEP / SAMPLE_RATE
# Its chroma filter and classifiers span 19 frames beyond the first, so a
# fingerprint has that many fewer frames than the audio.
FRAME_SPAN = 19

# Complete fingerprints of ARM's Opus tracks, and of generated audio, land
# exactly on expected_frames(). The truncations seen were 154 s and 224 s short.
TOLERANCE_FRAMES = 16


class IncompleteFingerprint(AnalysisError):
    """The fingerprint covers a different length of audio than the container says."""


@dataclass(frozen=True, slots=True)
class Fingerprint:
    # Chromaprint's raw 32-bit frames, one per FRAME_SECONDS.
    frames: tuple[int, ...]
    # The container's duration for the fingerprinted stream, which the frames
    # were checked against.
    duration: float

    @classmethod
    def from_text(cls, text: str, duration: float) -> "Fingerprint":
        """Read fpcalc's -raw -plain output, as stored in a fixture."""
        frames = tuple(int(f) & 0xFFFFFFFF for f in text.strip().split(","))
        check_complete(len(frames), duration)
        return cls(frames, duration)

    def to_text(self) -> str:
        return ",".join(map(str, self.frames)) + "\n"


def expected_frames(seconds: float) -> int:
    samples = int(seconds * SAMPLE_RATE)
    return max(0, (samples - FRAME_SAMPLES) // FRAME_STEP + 1 - FRAME_SPAN)


def check_complete(frames: int, seconds: float) -> None:
    """Refuse a fingerprint whose length disagrees with the container's.

    fpcalc's own reported duration is the container's, not what it decoded, so
    it cannot detect a short read. Counting frames can.
    """
    expected = expected_frames(seconds)
    if abs(frames - expected) > TOLERANCE_FRAMES:
        raise IncompleteFingerprint(
            f"{frames} frames ({frames * FRAME_SECONDS:.1f} s) where a"
            f" {seconds:.1f} s stream gives {expected}"
        )


def fingerprint(path: Path, probed: Probe | None = None) -> Fingerprint:
    """Fingerprint the first audio track, at 11,025 Hz mono, as measured."""
    probed = probed or probe(path)
    audio = probed.of_type("audio")
    if not audio:
        raise AnalysisError(f"{path} has no audio stream")
    duration = audio[0].duration or probed.duration
    if duration is None:
        raise AnalysisError(f"{path} gives no duration to check a fingerprint by")

    # ffmpeg chooses the track: fpcalc on its own takes av_find_best_stream's
    # choice, which need not be the first.
    with tempfile.TemporaryFile() as decode_errors:
        decode = subprocess.Popen(
            [
                "ffmpeg",
                "-nostdin",
                "-v",
                "error",
                "-i",
                str(path),
                "-map",
                "0:a:0",
                "-ac",
                "1",
                "-ar",
                str(SAMPLE_RATE),
                "-f",
                "s16le",
                "-",
            ],
            stdout=subprocess.PIPE,
            stderr=decode_errors,
        )
        assert decode.stdout is not None
        try:
            result = subprocess.run(
                [
                    "fpcalc",
                    "-raw",
                    "-plain",
                    "-length",
                    "0",
                    "-format",
                    "s16le",
                    "-rate",
                    str(SAMPLE_RATE),
                    "-channels",
                    "1",
                    "-",
                ],
                stdin=decode.stdout,
                capture_output=True,
                check=False,
            )
        finally:
            decode.stdout.close()
            decode.wait()
        decode_errors.seek(0)
        decode_stderr = decode_errors.read().decode(errors="replace").strip()

    if decode.returncode != 0:
        raise AnalysisError(f"ffmpeg exited {decode.returncode}: {decode_stderr}")
    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace").strip()
        raise AnalysisError(f"fpcalc exited {result.returncode}: {stderr}")
    return Fingerprint.from_text(result.stdout.decode(), duration)
