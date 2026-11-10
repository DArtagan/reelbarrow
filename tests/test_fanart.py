import httpx
import pytest

from reelbarrow.fanart import Art, Client, FanartError, MovieArt, Recorded, record

KEY = "not-a-real-fanart-key"
REPLY = {
    "name": "Monte Carlo or Bust!",
    "tmdb_id": "38792",
    "hdmovielogo": [
        {
            "id": "1",
            "url": "https://assets.fanart.tv/fanart/movies/38792/hdmovielogo/a.png",
            "lang": "en",
            "likes": "3",
            "width": "800",
        }
    ],
    "moviedisc": [
        {
            "id": "2",
            "url": "https://assets.fanart.tv/fanart/movies/38792/moviedisc/b.png",
            "lang": "00",
            "likes": "0",
            "disc": "1",
            "disc_type": "dvd",
        }
    ],
    "moviebanner": [{"id": "3", "url": "https://assets.fanart.tv/c.jpg", "lang": "en"}],
}


def fanart(requests: list[httpx.Request], status: int = 200) -> Client:
    def reply(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if status != 200:
            return httpx.Response(status, json={"error message": f"bad {KEY}"})
        if request.url.path == "/v3.2/movies/38792":
            return httpx.Response(200, json=REPLY)
        return httpx.Response(
            404, json={"status": "error", "error message": "Not found"}
        )

    return Client(KEY, transport=httpx.MockTransport(reply))


def test_the_key_goes_in_a_header_never_the_url():
    requests: list[httpx.Request] = []
    fanart(requests).movie(38792)
    (request,) = requests
    assert request.headers["api-key"] == KEY
    assert KEY not in str(request.url)
    assert str(request.url) == "https://webservice.fanart.tv/v3.2/movies/38792"


def test_a_films_art_with_its_counts_as_numbers():
    art = fanart([]).movie(38792)
    assert art.hdmovielogo == [
        Art(
            url="https://assets.fanart.tv/fanart/movies/38792/hdmovielogo/a.png",
            lang="en",
            likes=3,
        )
    ]
    assert art.moviedisc[0].lang == "00"


def test_a_film_fanart_tv_has_nothing_for_has_no_art():
    assert fanart([]).movie(1) == MovieArt()


def test_a_recording_keeps_only_what_a_sidecar_reads():
    assert record(fanart([]), 38792) == {
        "movies/38792": {
            "hdmovielogo": [
                {
                    "url": "https://assets.fanart.tv/fanart/movies/38792/hdmovielogo/a.png",
                    "lang": "en",
                    "likes": "3",
                }
            ],
            "moviedisc": [
                {
                    "url": "https://assets.fanart.tv/fanart/movies/38792/moviedisc/b.png",
                    "lang": "00",
                    "likes": "0",
                }
            ],
        }
    }


def test_a_recording_replays_as_the_service_would_have_read_it():
    replayed = Recorded(record(fanart([]), 38792))
    assert replayed.movie(38792) == fanart([]).movie(38792)
    with pytest.raises(FanartError, match="no recorded reply"):
        replayed.movie(1)


def test_an_error_names_the_status_and_not_the_key():
    with pytest.raises(FanartError) as raised:
        fanart([], status=401).movie(38792)
    assert "401" in str(raised.value)
    assert KEY not in str(raised.value)
