import subprocess
import tempfile
from collections.abc import Sequence


class AnalysisError(Exception):
    """A measurement could not be made, or its result cannot be trusted."""


def run(command: Sequence[str]) -> bytes:
    """Run a measuring tool and return its stdout, raising if it fails."""
    # A tool that cannot be started raises OSError, left uncaught. That is a
    # broken install, not a fact about the file, and as an AnalysisError it
    # would read as every file on the share failing to measure.
    result = subprocess.run(command, capture_output=True, check=False)
    _check(command, result.returncode, result.stderr)
    return result.stdout


def pipe(source: Sequence[str], sink: Sequence[str]) -> bytes:
    """Run `source | sink` and return the sink's stdout, raising as run() does.

    The source's output streams into the sink without passing through Python:
    a feature's decoded audio is hundreds of megabytes.
    """
    # The source's stderr goes to a file, not a pipe: nothing reads a pipe until
    # the sink exits, and a source that filled one would stall both.
    with tempfile.TemporaryFile() as source_stderr:
        producer = subprocess.Popen(
            source, stdout=subprocess.PIPE, stderr=source_stderr
        )
        assert producer.stdout is not None
        try:
            result = subprocess.run(
                sink, stdin=producer.stdout, capture_output=True, check=False
            )
        finally:
            producer.stdout.close()
            producer.wait()
        source_stderr.seek(0)
        _check(source, producer.returncode, source_stderr.read())
    _check(sink, result.returncode, result.stderr)
    return result.stdout


def _check(command: Sequence[str], returncode: int, stderr: bytes) -> None:
    if returncode != 0:
        message = stderr.decode(errors="replace").strip()
        raise AnalysisError(f"{command[0]} exited {returncode}: {message}")
