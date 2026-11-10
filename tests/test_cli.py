"""`reelbarrow analyse` and `reelbarrow plan`, run as the pod runs them, on a
tree laid out as the share is."""

import json
import os
import sys
from datetime import UTC, datetime, timedelta

import pytest

from reelbarrow import cli, tmdb

ARM = "import/automatic-ripping-machine"
START = datetime(2026, 9, 20, 19, 0, 21, tzinfo=UTC)
FINISH = datetime(2026, 9, 20, 21, 48, 45, tzinfo=UTC)
COMPLETED = f"{ARM}/completed/movies/A-Film (1969)"
MANIFEST = {
    "schema": 1,
    "source": "arm",
    "id": "34-178993082181",
    "state": "succeeded",
    "start_time": START.isoformat(),
    "finish_time": FINISH.isoformat(),
    "errors": None,
    "disc": {"type": "dvd", "label": "A_FILM", "crc64": "ef68a3c769a42a4f"},
    "identity": {
        field: {"value": value, "reason": "lookup"}
        for field, value in [
            ("title", "A-Film"),
            ("year", "1969"),
            ("imdb_id", "tt0064688"),
            ("kind", "movie"),
        ]
    },
    "completed": {"folder": {"path": COMPLETED}},
}
REPLIES = {
    "find/tt0064688": {"movie_results": [{"id": 38792}]},
    "movie/38792": {
        "id": 38792,
        "title": "A Film",
        "release_date": "1969-04-28",
        "runtime": 1,
        "imdb_id": "tt0064688",
    },
}


@pytest.fixture
def share(tmp_path, ffmpeg, monkeypatch):
    """A one-minute film, its raw copy written while its job ran, and its
    manifest; the environment set as the deployment sets it."""
    root = tmp_path / "video"
    film = ffmpeg(
        "film.mkv",
        *("-f", "lavfi", "-i", "testsrc=d=60:s=32x24:r=1", "-c:v", "ffv1"),
    )
    (root / COMPLETED).mkdir(parents=True)
    (root / COMPLETED / "A-Film (1969).mkv").write_bytes(film.read_bytes())
    raw = root / ARM / "raw" / "A-Film"
    raw.mkdir(parents=True)
    (raw / "B1_t00.mkv").write_bytes(film.read_bytes())
    during = (START + timedelta(hours=1)).timestamp()
    os.utime(raw / "B1_t00.mkv", (during, during))
    (root / "movies").mkdir()
    manifests = root / ARM / "manifests"
    manifests.mkdir()
    (manifests / "manifest-arm-34-178993082181.json").write_text(json.dumps(MANIFEST))
    running = {**MANIFEST, "id": "35-1", "state": "running", "finish_time": None}
    (manifests / "manifest-arm-35-1.json").write_text(json.dumps(running))
    monkeypatch.setenv("REELBARROW_VIDEO_ROOT", str(root))
    monkeypatch.setenv("REELBARROW_MANIFEST_DIR", str(manifests))
    monkeypatch.setenv("REELBARROW_TMDB_TOKEN", "eyJ-not-a-real-token")
    monkeypatch.setattr(tmdb, "Client", lambda token: tmdb.Recorded(REPLIES))
    return root


def run(monkeypatch, capsys, *args: str) -> tuple[int, str, str]:
    monkeypatch.setattr(sys, "argv", ["reelbarrow", *args])
    with pytest.raises(SystemExit) as exited:
        cli.main()
    captured = capsys.readouterr()
    return exited.value.code, captured.out, captured.err


def test_analyse_prints_the_document(share, monkeypatch, capsys):
    manifest = share / ARM / "manifests" / "manifest-arm-34-178993082181.json"
    code, out, _ = run(monkeypatch, capsys, "analyse", str(manifest))
    document = json.loads(out)
    assert code == 0
    assert document["completed"]["path"] == COMPLETED
    assert [f["found"] for f in document["raw"]] == ["written_during_run"]


def test_plan_with_no_path_plans_every_manifest_but_the_running(
    share, monkeypatch, capsys
):
    code, out, _ = run(monkeypatch, capsys, "plan", "--json")
    (plan,) = json.loads(out)
    assert code == 0
    assert plan["id"] == "34-178993082181"
    assert plan["gate"] == "automatic", plan["checks"]
    assert plan["operations"][0]["path"] == "movies/A Film (1969) {tmdb-38792}"


def test_plan_prints_each_plan_for_a_person(share, monkeypatch, capsys):
    code, out, _ = run(monkeypatch, capsys, "plan")
    assert code == 0
    assert "arm 34-178993082181: automatic" in out
    assert "arm 35-1: running, not planned yet" in out


def test_plan_needs_tmdb(share, monkeypatch, capsys):
    monkeypatch.delenv("REELBARROW_TMDB_TOKEN")
    code, _, err = run(monkeypatch, capsys, "plan")
    assert code == 2
    assert "REELBARROW_TMDB_TOKEN" in err


def test_plan_changes_nothing_on_the_share(share, monkeypatch, capsys):
    before = sorted(
        (str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in share.rglob("*")
    )
    run(monkeypatch, capsys, "plan")
    after = sorted(
        (str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in share.rglob("*")
    )
    assert after == before
