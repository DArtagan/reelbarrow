import pytest

from reelbarrow.config import Settings


def test_dry_run_unless_set_to_false(monkeypatch):
    monkeypatch.delenv("REELBARROW_DRY_RUN", raising=False)
    assert Settings().dry_run is True
    monkeypatch.setenv("REELBARROW_DRY_RUN", "false")
    assert Settings().dry_run is False


@pytest.mark.parametrize(
    "name", ["TMDB_TOKEN", "FANART_KEY", "PLEX_URL", "PLEX_TOKEN", "PLEX_PATHS"]
)
def test_a_variable_compose_passes_on_empty_is_unset(monkeypatch, name):
    monkeypatch.setenv(f"REELBARROW_{name}", "")
    assert not getattr(Settings(), name.lower())


def test_plex_paths_are_json(monkeypatch):
    monkeypatch.setenv("REELBARROW_PLEX_PATHS", '{"movies": "/data/movies"}')
    assert Settings().plex_paths == {"movies": "/data/movies"}
