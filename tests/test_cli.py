"""`reelbarrow analyse`, `plan` and `file`, run as the pod runs them, on a
tree laid out as the share is."""

import json
import os
import sys
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from reelbarrow import cli, fanart, plex, sidecars, tmdb

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
    "movie/38792/credits": {"cast": [], "crew": []},
    "movie/38792/images": {
        "posters": [{"file_path": "/poster.jpg", "iso_639_1": "en"}],
        "backdrops": [],
        "logos": [],
    },
}
FILM = "movies/A Film (1969) {tmdb-38792}"


class Images:
    def fetch(self, url: str) -> bytes:
        return sidecars.MAGIC[".jpg"] + url.encode()


@pytest.fixture
def share(tmp_path, ffmpeg, monkeypatch, guarded):
    """A one-minute film, its raw copy written while its job ran, and its
    manifest; the environment set as the deployment sets it."""
    root = tmp_path / "video"
    guarded(root)
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
    monkeypatch.setenv("REELBARROW_FANART_KEY", "not-a-real-key")
    monkeypatch.setenv("REELBARROW_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("REELBARROW_DRY_RUN", raising=False)
    monkeypatch.setattr(tmdb, "Client", lambda token: tmdb.Recorded(REPLIES))
    monkeypatch.setattr(
        fanart, "Client", lambda key: fanart.Recorded({"movies/38792": {}})
    )
    monkeypatch.setattr(sidecars, "HttpImages", Images)
    return root


def listing(root):
    return sorted(
        (str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in root.rglob("*")
    )


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
    before = listing(share)
    run(monkeypatch, capsys, "plan")
    assert listing(share) == before


# `reelbarrow file`: in dry run, as the deployed pod runs it, and live.


def test_file_in_dry_run_reports_every_change_refused(share, monkeypatch, capsys):
    before = listing(share)
    code, out, _ = run(monkeypatch, capsys, "file")
    assert code == 0
    assert out.startswith("Dry run: every change is refused.")
    assert "arm 34-178993082181: dry_run" in out
    assert f"refused  make_folder   {FILM}" in out
    assert "refused  record" in out
    assert f"refused  plex_scan     {FILM}" in out
    assert "arm 35-1: running, not planned yet" in out
    assert listing(share) == before


def test_file_as_json_gives_each_plan_and_its_report(share, monkeypatch, capsys):
    code, out, _ = run(monkeypatch, capsys, "file", "--json")
    (filed,) = json.loads(out)
    assert code == 0
    assert filed["plan"]["gate"] == "automatic"
    assert filed["report"]["result"] == "dry_run"
    outcomes = {step["outcome"] for step in filed["report"]["steps"][1:]}
    assert outcomes <= {"refused", "skipped"}


def test_file_leaves_a_plan_for_review_alone(share, monkeypatch, capsys):
    longer = {**REPLIES, "movie/38792": {**REPLIES["movie/38792"], "runtime": 2}}
    monkeypatch.setattr(tmdb, "Client", lambda token: tmdb.Recorded(longer))
    monkeypatch.setenv("REELBARROW_DRY_RUN", "false")
    monkeypatch.setenv("REELBARROW_PLEX_URL", "http://plex:32400")
    monkeypatch.setenv("REELBARROW_PLEX_TOKEN", "not-a-real-token")
    monkeypatch.setenv("REELBARROW_PLEX_PATHS", '{"movies": "/data/movies"}')
    before = listing(share)
    code, out, _ = run(monkeypatch, capsys, "file")
    assert code == 0
    assert "arm 34-178993082181: review" in out
    assert "left for review" in out
    assert listing(share) == before


def test_file_needs_fanart_tv(share, monkeypatch, capsys):
    monkeypatch.delenv("REELBARROW_FANART_KEY")
    code, _, err = run(monkeypatch, capsys, "file")
    assert code == 2
    assert "REELBARROW_FANART_KEY" in err


def test_file_live_needs_plex(share, monkeypatch, capsys):
    monkeypatch.setenv("REELBARROW_DRY_RUN", "false")
    before = listing(share)
    code, _, err = run(monkeypatch, capsys, "file")
    assert code == 2
    for name in ("PLEX_URL", "PLEX_TOKEN", "PLEX_PATHS"):
        assert f"REELBARROW_{name} is not set" in err
    assert listing(share) == before


def test_file_live_files_the_film_and_scans_it(share, monkeypatch, capsys):
    scanned = []

    def reply(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/library/sections":
            directory = {"key": "1", "Location": [{"path": "/data/movies"}]}
            return httpx.Response(
                200, json={"MediaContainer": {"Directory": [directory]}}
            )
        scanned.append(request.url.params["path"])
        return httpx.Response(200)

    # A subclass, not a function: the CLI imports the executor lazily, and a
    # module first imported under this patch binds whatever `Plex` is then.
    class FakePlex(plex.Plex):
        def __init__(self, *args):
            super().__init__(*args, transport=httpx.MockTransport(reply))

    monkeypatch.setattr(plex, "Plex", FakePlex)
    monkeypatch.setenv("REELBARROW_DRY_RUN", "false")
    monkeypatch.setenv("REELBARROW_PLEX_URL", "http://plex:32400")
    monkeypatch.setenv("REELBARROW_PLEX_TOKEN", "not-a-real-token")
    monkeypatch.setenv("REELBARROW_PLEX_PATHS", '{"movies": "/data/movies"}')

    code, out, _ = run(monkeypatch, capsys, "file")
    assert code == 0, out
    assert out.startswith("Filing is live.")
    assert "arm 34-178993082181: filed" in out
    assert (share / FILM / "A Film (1969).mkv").exists()
    assert (share / FILM / "poster.jpg").exists()
    assert not (share / COMPLETED).exists()
    assert scanned == [f"/data/{FILM}"]
    (record,) = (share / FILM / "raw").glob("*/filing-arm-34-178993082181.json")
    document = json.loads(record.read_text())
    assert document["result"] == "filed"
    # Planning's replies and filing's, from the unit's one client.
    assert set(document["replies"]["tmdb"]) == set(REPLIES)
    assert document["analysis"]["id"] == "34-178993082181"

    # A second run finds the share says it was filed: its manifest's files
    # have moved and its film is in the library, so its plan is for review.
    code, out, _ = run(monkeypatch, capsys, "file")
    assert "arm 34-178993082181: review" in out
