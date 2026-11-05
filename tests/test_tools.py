import pytest

from reelbarrow.analysis.tools import AnalysisError, pipe, run


def sh(script: str) -> list[str]:
    return ["sh", "-c", script]


def test_run_returns_stdout():
    assert run(sh("printf measured")) == b"measured"


def test_a_failing_tool_raises_with_its_stderr():
    with pytest.raises(AnalysisError, match="sh exited 3: no such title"):
        run(sh("echo 'no such title' >&2; exit 3"))


def test_a_tool_that_cannot_start_is_not_an_analysis_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        run([str(tmp_path / "absent-tool")])


def test_pipe_feeds_the_source_into_the_sink():
    assert pipe(sh("printf 'a\\nb\\n'"), ["wc", "-l"]).strip() == b"2"


def test_pipe_reports_a_failing_source():
    with pytest.raises(AnalysisError, match="sh exited 1: decode failed"):
        pipe(sh("echo 'decode failed' >&2; exit 1"), ["cat"])


def test_pipe_reports_a_failing_sink():
    with pytest.raises(AnalysisError, match="sh exited 2: bad input"):
        pipe(["true"], sh("cat >/dev/null; echo 'bad input' >&2; exit 2"))


def test_a_source_with_a_lot_to_say_does_not_stall_the_pipe():
    # 1 MiB of stderr, far past what a pipe buffers.
    noisy = sh("head -c 1048576 /dev/zero | tr '\\0' x >&2; printf done")
    assert pipe(noisy, ["cat"]) == b"done"
