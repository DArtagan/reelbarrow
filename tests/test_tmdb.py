import httpx
import pytest

from reelbarrow.tmdb import Client, Movie, Recorded, TmdbError, record

TOKEN = "eyJ-not-a-real-token"

FIND = {
    "movie_results": [{"id": 38792, "title": "Monte Carlo or Bust!", "popularity": 1}],
    "tv_results": [],
}
MOVIE = {
    "id": 38792,
    "title": "Monte Carlo or Bust!",
    "original_title": "Monte Carlo or Bust!",
    "release_date": "1969-04-28",
    "runtime": 122,
    "imdb_id": "tt0064688",
    "overview": "A long overview no rule reads.",
}


def tmdb(requests: list[httpx.Request], status: int = 200) -> Client:
    def reply(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if status != 200:
            return httpx.Response(status, json={"status_message": f"bad {TOKEN}"})
        if request.url.path == "/3/find/tt0064688":
            return httpx.Response(200, json=FIND)
        if request.url.path == "/3/movie/38792":
            return httpx.Response(200, json=MOVIE)
        return httpx.Response(404, json={})

    return Client(TOKEN, transport=httpx.MockTransport(reply))


def test_the_token_goes_in_a_header_never_the_url():
    requests: list[httpx.Request] = []
    tmdb(requests).movies_for_imdb("tt0064688")
    (request,) = requests
    assert request.headers["authorization"] == f"Bearer {TOKEN}"
    assert TOKEN not in str(request.url)
    assert request.url.params["external_source"] == "imdb_id"
    assert request.url.params["language"] == "en-US"


def test_a_film_by_its_imdb_id():
    client = tmdb([])
    assert client.movies_for_imdb("tt0064688") == [38792]
    movie = client.movie(38792)
    assert movie == Movie(
        id=38792,
        title="Monte Carlo or Bust!",
        release_date="1969-04-28",
        runtime=122,
        imdb_id="tt0064688",
    )
    assert movie.year == 1969


def test_a_recording_keeps_only_what_a_rule_reads():
    assert record(tmdb([]), "tt0064688") == {
        "find/tt0064688": {"movie_results": [{"id": 38792}]},
        "movie/38792": {
            "id": 38792,
            "title": "Monte Carlo or Bust!",
            "release_date": "1969-04-28",
            "runtime": 122,
            "imdb_id": "tt0064688",
        },
    }


def test_a_recording_replays_as_the_service_would_have_read_it():
    recording = record(tmdb([]), "tt0064688")
    replayed = Recorded(recording)
    assert replayed.movies_for_imdb("tt0064688") == [38792]
    assert replayed.movie(38792) == tmdb([]).movie(38792)
    with pytest.raises(TmdbError, match="no recorded reply"):
        replayed.movie(1)


def test_an_error_names_the_status_and_not_the_token():
    with pytest.raises(TmdbError) as raised:
        tmdb([], status=401).movie(38792)
    assert "401" in str(raised.value)
    assert TOKEN not in str(raised.value)


@pytest.mark.parametrize(
    ("date", "year"), [("1969-04-28", 1969), ("", None), (None, None)]
)
def test_a_year_only_from_a_release_date(date, year):
    assert Movie(id=1, title="x", release_date=date).year == year
