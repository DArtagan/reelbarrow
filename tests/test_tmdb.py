import httpx
import pytest

from reelbarrow.tmdb import CAST, Client, Movie, Recorded, TmdbError, record

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
    "overview": "Sequel to an earlier race.",
    "popularity": 1.5,
    "genres": [{"id": 35, "name": "Comedy"}],
    "production_companies": [{"id": 4, "name": "Paramount", "logo_path": None}],
}
CREDITS = {
    "id": 38792,
    "cast": [
        {"name": f"Actor {n}", "character": f"Role {n}", "order": n, "id": n}
        for n in reversed(range(CAST + 2))
    ],
    "crew": [
        {"name": "Ken Annakin", "job": "Director", "department": "Directing"},
        {"name": "Jack Davies", "job": "Screenplay", "department": "Writing"},
        {"name": "A Grip", "job": "Grip", "department": "Crew"},
    ],
}
IMAGES = {
    "id": 38792,
    "posters": [
        {
            "file_path": "/p.jpg",
            "iso_639_1": "en",
            "vote_average": 5.2,
            "vote_count": 3,
            "width": 2000,
            "aspect_ratio": 0.667,
        }
    ],
    "backdrops": [{"file_path": "/b.jpg", "iso_639_1": None, "width": 1920}],
    "logos": [],
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
        if request.url.path == "/3/movie/38792/credits":
            return httpx.Response(200, json=CREDITS)
        if request.url.path == "/3/movie/38792/images":
            return httpx.Response(200, json=IMAGES)
        return httpx.Response(404, json={})

    return Client(TOKEN, transport=httpx.MockTransport(reply))


def test_the_token_goes_in_a_header_never_the_url():
    requests: list[httpx.Request] = []
    tmdb(requests).movie_ids_for_imdb("tt0064688")
    (request,) = requests
    assert request.headers["authorization"] == f"Bearer {TOKEN}"
    assert TOKEN not in str(request.url)
    assert request.url.params["external_source"] == "imdb_id"
    assert request.url.params["language"] == "en-US"


def test_a_film_by_its_imdb_id():
    client = tmdb([])
    assert client.movie_ids_for_imdb("tt0064688") == [38792]
    movie = client.movie(38792)
    assert movie == Movie(
        id=38792,
        title="Monte Carlo or Bust!",
        release_date="1969-04-28",
        runtime=122,
        imdb_id="tt0064688",
    )
    assert movie.year == 1969


def test_a_recording_keeps_only_what_a_rule_or_a_sidecar_reads():
    recording = record(tmdb([]), "tt0064688")
    assert recording["find/tt0064688"] == {"movie_results": [{"id": 38792}]}
    assert recording["movie/38792"] == {
        "id": 38792,
        "title": "Monte Carlo or Bust!",
        "original_title": "Monte Carlo or Bust!",
        "release_date": "1969-04-28",
        "runtime": 122,
        "imdb_id": "tt0064688",
        "overview": "Sequel to an earlier race.",
        "genres": [{"name": "Comedy"}],
        "production_companies": [{"name": "Paramount"}],
    }
    assert recording["movie/38792/images"] == {
        "posters": [
            {
                "file_path": "/p.jpg",
                "iso_639_1": "en",
                "vote_average": 5.2,
                "vote_count": 3,
            }
        ],
        "backdrops": [{"file_path": "/b.jpg", "iso_639_1": None}],
        "logos": [],
    }


def test_credits_keep_the_billed_cast_and_who_directed_and_wrote():
    credits = record(tmdb([]), "tt0064688")["movie/38792/credits"]
    assert [member["order"] for member in credits["cast"]] == list(range(CAST))
    assert credits["cast"][0] == {"name": "Actor 0", "character": "Role 0", "order": 0}
    assert credits["crew"] == [
        {"name": "Ken Annakin", "job": "Director"},
        {"name": "Jack Davies", "job": "Screenplay"},
    ]


def test_images_are_asked_for_in_english_or_without_text():
    requests: list[httpx.Request] = []
    tmdb(requests).images(38792)
    (request,) = requests
    assert request.url.params["include_image_language"] == "en,null"


def test_a_recording_replays_as_the_service_would_have_read_it():
    recording = record(tmdb([]), "tt0064688")
    replayed = Recorded(recording)
    assert replayed.movie_ids_for_imdb("tt0064688") == [38792]
    assert replayed.movie(38792) == tmdb([]).movie(38792)
    assert replayed.details(38792) == tmdb([]).details(38792)
    assert replayed.credits(38792) == tmdb([]).credits(38792)
    assert replayed.images(38792) == tmdb([]).images(38792)
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
