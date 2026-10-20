import subprocess
from collections.abc import Sequence


class AnalysisError(Exception):
    """A measurement could not be made, or its result cannot be trusted."""


def run(command: Sequence[str]) -> bytes:
    """Run a measuring tool and return its stdout, raising on any failure."""
    try:
        result = subprocess.run(command, capture_output=True, check=False)
    except OSError as error:
        raise AnalysisError(f"{command[0]}: {error}") from error
    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace").strip()
        raise AnalysisError(f"{command[0]} exited {result.returncode}: {stderr}")
    return result.stdout
