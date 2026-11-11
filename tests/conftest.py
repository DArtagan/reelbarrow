import json
import subprocess
from pathlib import Path

import pytest
import share_guard

from reelbarrow.analysis.fingerprint import Fingerprint

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures() -> Path:
    return FIXTURES


@pytest.fixture(scope="session")
def fingerprints() -> dict[str, Fingerprint]:
    """The committed fingerprints, each of the first audio track of an ARM
    transcode, checked against that track's duration as it loads: Robin Hood's
    two cuts, and the two films on The Rescuers' disc."""
    directory = FIXTURES / "fingerprints"
    durations = json.loads((directory / "durations.json").read_text())
    return {
        name: Fingerprint.from_text((directory / f"{name}.fp").read_text(), duration)
        for name, duration in durations.items()
    }


@pytest.fixture
def guarded():
    """Guards a video root for the test: anything reelbarrow changes under it,
    other than through the executor, fails the test (`share_guard`)."""
    guards = []

    def guard(root: Path) -> share_guard.Guard:
        made = share_guard.guard(root)
        guards.append(made)
        return made

    yield guard
    violations = [v for made in guards for v in share_guard.release(made)]
    assert not violations, "written under the video root: " + "; ".join(violations)


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
