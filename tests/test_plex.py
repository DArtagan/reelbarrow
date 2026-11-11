import httpx
import pytest

from reelbarrow.plex import Plex, PlexError

TOKEN = "not-a-real-plex-token"
SECTIONS = {
    "MediaContainer": {
        "Directory": [
            {"key": "1", "type": "movie", "Location": [{"path": "/data/movies"}]},
            {"key": "2", "type": "show", "Location": [{"path": "/data/shows"}]},
        ]
    }
}


def plex(requests: list[httpx.Request], sections=SECTIONS, status: int = 200) -> Plex:
    def reply(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if status != 200:
            return httpx.Response(status)
        if request.url.path == "/library/sections":
            return httpx.Response(200, json=sections)
        return httpx.Response(200)

    return Plex(
        "http://plex:32400",
        TOKEN,
        {"movies": "/data/movies", "shows": "/data/shows"},
        transport=httpx.MockTransport(reply),
    )


def test_a_folder_is_scanned_in_the_section_holding_it():
    requests: list[httpx.Request] = []
    detail = plex(requests).scan("movies/Monte Carlo or Bust! (1969) {tmdb-38792}")
    sections, refresh = requests
    assert sections.url.path == "/library/sections"
    assert refresh.url.path == "/library/sections/1/refresh"
    assert (
        refresh.url.params["path"]
        == "/data/movies/Monte Carlo or Bust! (1969) {tmdb-38792}"
    )
    assert detail.startswith("section 1 scanning /data/movies/")


def test_the_token_goes_in_a_header_never_the_url():
    requests: list[httpx.Request] = []
    plex(requests).scan("movies/A (1969)")
    for request in requests:
        assert request.headers["x-plex-token"] == TOKEN
        assert TOKEN not in str(request.url)


def test_a_folder_plex_doesnt_mount_is_refused():
    with pytest.raises(PlexError, match="isn't in a library"):
        plex([]).scan("import/automatic-ripping-machine/completed")
    with pytest.raises(PlexError, match="isn't in a library"):
        plex([]).scan("moviesque/A (1969)")


def test_no_section_holding_the_folder_is_an_error():
    only_shows = {
        "MediaContainer": {"Directory": SECTIONS["MediaContainer"]["Directory"][1:]}
    }
    with pytest.raises(PlexError, match="0 of Plex's sections"):
        plex([], sections=only_shows).scan("movies/A (1969)")


def test_an_error_names_the_status_and_not_the_token():
    with pytest.raises(PlexError) as raised:
        plex([], status=401).scan("movies/A (1969)")
    assert "401" in str(raised.value)
    assert TOKEN not in str(raised.value)
