from pathlib import Path

from reelbarrow.analysis.tools import AnalysisError, run


def video_md5(path: Path) -> str:
    """MD5 of the video stream's packets, with no decoding.

    Equal hashes mean interchangeable files: the encoder ARM runs is
    deterministic for identical input, and the hash ignores the container,
    audio and subtitles.
    """
    output = run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            "0:v",
            "-c",
            "copy",
            "-f",
            "md5",
            "-",
        ]
    ).decode()
    key, _, digest = output.strip().partition("=")
    if key != "MD5" or len(digest) != 32:
        raise AnalysisError(f"ffmpeg md5 output not understood: {output!r}")
    return digest
