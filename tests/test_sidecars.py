"""Sidecars rendered from their sources: Kodi's NFO from TMDB's record, and
artwork from TMDB and fanart.tv, chosen in a fixed order."""

import json
import xml.etree.ElementTree as ET

import cases
import httpx
import pytest

from reelbarrow import fanart, tmdb
from reelbarrow.plan import Sidecar, Write
from reelbarrow.sidecars import (
    MAGIC,
    TMDB_IMAGES,
    HttpImages,
    SidecarError,
    Sources,
    render,
)

FOLDER = "movies/Monte Carlo or Bust! (1969) {tmdb-38792}"
JPG, PNG = MAGIC[".jpg"], MAGIC[".png"]


class Images:
    def __init__(self, served: dict[str, bytes | None] | None = None) -> None:
        self.served = served or {}
        self.fetched: list[str] = []

    def fetch(self, url: str) -> bytes | None:
        self.fetched.append(url)
        if url in self.served:
            return self.served[url]
        return (JPG if url.endswith(".jpg") else PNG) + url.encode()


def sources(
    tmdb_replies: dict | None = None,
    fanart_replies: dict | None = None,
    images: Images | None = None,
) -> Sources:
    case = cases.load("dvd-film-raw-unrecorded")
    return Sources(
        tmdb=tmdb.Recorded(tmdb_replies or case.tmdb_replies),
        fanart=fanart.Recorded(fanart_replies or {"movies/38792": {}}),
        images=images or Images(),
    )


def artwork(kind: str, suffix: str = ".jpg") -> Write:
    return Write(
        path=f"{FOLDER}/{kind}{suffix}",
        sidecar=Sidecar.ARTWORK,
        reason="artwork",
        content={"tmdb_id": 38792, "kind": kind},
    )


NFO = Write(
    path=f"{FOLDER}/movie.nfo",
    sidecar=Sidecar.MOVIE_NFO,
    reason="the identification",
    content={"tmdb_id": 38792, "imdb_id": "tt0064688"},
)


def test_the_nfo_holds_the_identification_in_kodis_schema():
    rendered = render(NFO, sources())
    movie = ET.fromstring(rendered.content)
    assert rendered.content.startswith(b"<?xml version='1.0' encoding='UTF-8'?>")
    assert movie.tag == "movie"
    assert movie.findtext("title") == "Monte Carlo or Bust!"
    assert movie.findtext("year") == "1969"
    assert movie.findtext("premiered") == "1969-04-28"
    assert movie.findtext("runtime") == "122"
    tmdb_id = movie.find("uniqueid[@type='tmdb']")
    assert (tmdb_id.text, tmdb_id.get("default")) == ("38792", "true")
    assert movie.find("uniqueid[@type='imdb']").text == "tt0064688"
    assert [g.text for g in movie.findall("genre")] == ["Adventure", "Comedy"]
    assert [d.text for d in movie.findall("director")] == ["Ken Annakin"]
    assert [c.text for c in movie.findall("credits")] == ["Jack Davies", "Ken Annakin"]
    actors = movie.findall("actor")
    assert len(actors) == 10
    assert (actors[0].findtext("name"), actors[0].findtext("role")) == (
        "Bourvil",
        "Monsieur Dupont",
    )


def test_the_nfo_keeps_tmdbs_own_spelling():
    # Only names on the share are folded to ASCII; the NFO is UTF-8.
    movie = ET.fromstring(render(NFO, sources()).content)
    assert "Gert Fröbe" in [a.findtext("name") for a in movie.findall("actor")]


def test_an_imdb_id_tmdb_no_longer_gives_stops_the_filing():
    replies = cases.load("dvd-film-raw-unrecorded").tmdb_replies
    changed = {**replies, "movie/38792": {**replies["movie/38792"], "imdb_id": "tt1"}}
    with pytest.raises(SidecarError, match="tt1"):
        render(NFO, sources(tmdb_replies=changed))


def test_disc_json_is_the_plans_document():
    content = {"schema": 1, "titles": [{"raw": "B1_t00.mkv", "file": "../../A.mkv"}]}
    write = Write(
        path=f"{FOLDER}/raw/X/disc.json",
        sidecar=Sidecar.DISC_JSON,
        reason="the disc",
        content=content,
    )
    assert json.loads(render(write, sources()).content) == content


def test_an_ignore_marker_is_empty():
    write = Write(
        path=f"{FOLDER}/raw/.nomedia", sidecar=Sidecar.IGNORE_MARKER, reason="marker"
    )
    assert render(write, sources()).content == b""


# Artwork.


def test_the_poster_is_tmdbs_best_voted_english_one():
    images = Images()
    rendered = render(artwork("poster"), sources(images=images))
    # Of job 34's four English posters, the one voted 8.596.
    assert images.fetched == [f"{TMDB_IMAGES}/21mBl3ohfohEdvfbNcHEbxmXVkX.jpg"]
    assert rendered.content.startswith(JPG)
    assert "TMDB's /21mBl3ohfohEdvfbNcHEbxmXVkX.jpg" in rendered.detail


def test_the_backdrop_is_one_without_text():
    images = Images()
    render(artwork("fanart"), sources(images=images))
    (url,) = images.fetched
    replies = cases.load("dvd-film-raw-unrecorded").tmdb_replies
    textless = [
        b["file_path"]
        for b in replies["movie/38792/images"]["backdrops"]
        if b["iso_639_1"] is None
    ]
    assert url.removeprefix(TMDB_IMAGES) in textless


def art(url: str, lang: str, likes: str) -> dict:
    return {"url": url, "lang": lang, "likes": likes}


FANART = {
    "movies/38792": {
        "hdmovielogo": [
            art(
                "https://assets.fanart.tv/fanart/movies/38792/hdmovielogo/fr.png",
                "fr",
                "9",
            ),
            art(
                "https://assets.fanart.tv/fanart/movies/38792/hdmovielogo/en-1.png",
                "en",
                "1",
            ),
            art(
                "https://assets.fanart.tv/fanart/movies/38792/hdmovielogo/en-3.png",
                "en",
                "3",
            ),
        ],
        "moviedisc": [
            art(
                "https://assets.fanart.tv/fanart/movies/38792/moviedisc/00.png",
                "00",
                "0",
            ),
        ],
        "hdmovieclearart": [
            art(
                "https://assets.fanart.tv/fanart/movies/38792/hdmovieclearart/de.png",
                "de",
                "4",
            ),
        ],
    }
}


def test_a_logo_is_fanart_tvs_most_liked_english_one():
    images = Images()
    render(artwork("clearlogo", ".png"), sources(fanart_replies=FANART, images=images))
    assert images.fetched == [
        "https://assets.fanart.tv/fanart/movies/38792/hdmovielogo/en-3.png"
    ]


def test_art_without_text_is_used_where_there_is_no_english():
    images = Images()
    render(artwork("disc", ".png"), sources(fanart_replies=FANART, images=images))
    assert images.fetched == [
        "https://assets.fanart.tv/fanart/movies/38792/moviedisc/00.png"
    ]


def test_art_in_another_language_is_never_used():
    rendered = render(artwork("clearart", ".png"), sources(fanart_replies=FANART))
    assert rendered.content is None
    assert rendered.detail == "neither TMDB nor fanart.tv has a clearart"


def test_an_image_gone_or_not_its_format_gives_way_to_the_next():
    gone = "https://assets.fanart.tv/fanart/movies/38792/hdmovielogo/en-3.png"
    wrong = "https://assets.fanart.tv/fanart/movies/38792/hdmovielogo/en-1.png"
    images = Images({gone: None, wrong: JPG + b"a jpeg named .png"})
    rendered = render(
        artwork("clearlogo", ".png"), sources(fanart_replies=FANART, images=images)
    )
    assert rendered.content is None
    assert "en-3.png is gone" in rendered.detail
    assert "en-1.png isn't a .png" in rendered.detail


def test_an_artwork_the_plan_doesnt_name_stops_the_filing():
    write = artwork("banner")
    with pytest.raises(SidecarError):
        render(write, sources())


# Fetching.


def test_images_come_only_from_the_providers_hosts():
    with pytest.raises(SidecarError, match="artwork host"):
        HttpImages().fetch("https://example.com/poster.jpg")


def test_an_image_link_over_http_is_fetched_over_https():
    seen = []

    def reply(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        return httpx.Response(200, content=PNG)

    images = HttpImages(transport=httpx.MockTransport(reply))
    assert images.fetch("http://assets.fanart.tv/fanart/a.png") == PNG
    assert seen[0].scheme == "https"


@pytest.mark.parametrize(("status", "found"), [(404, None)])
def test_an_image_the_provider_no_longer_has_is_none(status, found):
    images = HttpImages(transport=httpx.MockTransport(lambda r: httpx.Response(status)))
    assert images.fetch(f"{TMDB_IMAGES}/x.jpg") is found


def test_any_other_failure_stops_the_filing():
    images = HttpImages(transport=httpx.MockTransport(lambda r: httpx.Response(503)))
    with pytest.raises(SidecarError, match="503"):
        images.fetch(f"{TMDB_IMAGES}/x.jpg")
