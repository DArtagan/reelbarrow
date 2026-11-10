from fastapi.testclient import TestClient

from reelbarrow.config import Settings
from reelbarrow.web import create_app


def test_dry_run_unless_disabled(monkeypatch):
    monkeypatch.delenv("REELBARROW_DRY_RUN", raising=False)
    assert Settings().dry_run is True


def test_dry_run_disabled_explicitly(monkeypatch):
    monkeypatch.setenv("REELBARROW_DRY_RUN", "false")
    assert Settings().dry_run is False


def test_healthz_reports_mode():
    client = TestClient(create_app(Settings(dry_run=True)))
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "dry_run": True}


def test_index_states_dry_run():
    client = TestClient(create_app(Settings(dry_run=True)))
    assert "nothing on the share is changed" in client.get("/").text


def test_an_empty_tmdb_token_is_none(monkeypatch):
    monkeypatch.setenv("REELBARROW_TMDB_TOKEN", "")
    assert Settings().tmdb_token is None


def test_the_tmdb_token_is_kept_out_of_reprs(monkeypatch):
    monkeypatch.setenv("REELBARROW_TMDB_TOKEN", "eyJ-secret")
    settings = Settings()
    assert settings.tmdb_token.get_secret_value() == "eyJ-secret"
    assert "eyJ-secret" not in repr(settings)
