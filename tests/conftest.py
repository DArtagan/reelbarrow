import json
import subprocess
from pathlib import Path

import pytest

from reelbarrow.analysis.fingerprint import Fingerprint

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures() -> Path:
    return FIXTURES


@pytest.fixture(scope="session")
def fingerprints() -> dict[str, Fingerprint]:
    """The committed fingerprints, each of the first audio track of an ARM
    transcode, checked against that track's duration as it loads."""
    directory = FIXTURES / "fingerprints"
    sources = json.loads((directory / "sources.json").read_text())
    return {
        name: Fingerprint.from_text(
            (directory / f"{name}.fp").read_text(), source["duration"]
        )
        for name, source in sources.items()
    }


@pytest.fixture
def ffmpeg(tmp_path):
    """Make a media file in tmp_path from ffmpeg arguments; returns its path."""

    def make(name: str, *args: str) -> Path:
        path = tmp_path / name
        subprocess.run(
            ["ffmpeg", "-nostdin", "-v", "error", "-y", *args, str(path)],
            check=True,
        )
        return path

    return make
