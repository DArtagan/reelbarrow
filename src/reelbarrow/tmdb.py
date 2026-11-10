"""TMDB, for what a film is called, how long it runs, and what its NFO and
artwork hold.

Only the fields a rule or a sidecar reads are kept from TMDB's replies, and a
fixture records those replies in TMDB's own shape, trimmed, so the tests
replay exactly what the service would have parsed. `python -m reelbarrow.tmdb
<imdb_id>` prints such a recording, made with the token in the environment.
"""

import json
import sys
from collections.abc import Mapping
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, ConfigDict

API = "https://api.themoviedb.org/3"
# Titles as an English-language library names them, whatever the environment.
LANGUAGE = "en-US"
# Images in English or with no language, the textless backdrops among them.
IMAGE_LANGUAGES = "en,null"
# What a film's NFO lists of its cast, in billing order.
CAST = 10
# The crew an NFO names: its <director> and its <credits>.
DIRECTING = frozenset({"Director"})
WRITING = frozenset({"Screenplay", "Writer", "Story", "Novel", "Author"})


class TmdbError(Exception):
    """TMDB could not be asked, or gave a reply that isn't understood."""


class Movie(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    id: int
    title: str
    # YYYY-MM-DD, or empty when TMDB has none.
    release_date: str | None = None
    # Minutes. TMDB gives 0 for unknown.
    runtime: int | None = None
    imdb_id: str | None = None

    @property
    def year(self) -> int | None:
        date = self.release_date or ""
        return int(date[:4]) if date[:4].isdigit() else None


class Named(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    name: str


class Details(Movie):
    """What a film's NFO says of it, beyond what identifies it."""

    original_title: str | None = None
    overview: str | None = None
    tagline: str | None = None
    genres: list[Named] = []
    production_companies: list[Named] = []
    production_countries: list[Named] = []


class CastMember(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    name: str
    character: str | None = None
    order: int


class CrewMember(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    name: str
    job: str


class Credits(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    cast: list[CastMember] = []
    crew: list[CrewMember] = []


class Image(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    file_path: str
    # Null: no language, which for a backdrop means no text on it.
    iso_639_1: str | None = None
    vote_average: float = 0.0
    vote_count: int = 0


class Images(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    posters: list[Image] = []
    backdrops: list[Image] = []
    logos: list[Image] = []


# What is kept of each reply, so a recording holds what a rule reads.
_FIND_FIELDS = ("id",)
_MOVIE_FIELDS = tuple(Details.model_fields)
_NAMED_FIELDS = ("genres", "production_companies", "production_countries")
_IMAGE_FIELDS = tuple(Image.model_fields)


def _trim_find(reply: Mapping[str, Any]) -> dict:
    return {
        "movie_results": [
            {k: r[k] for k in _FIND_FIELDS if k in r}
            for r in reply.get("movie_results", [])
        ]
    }


def _trim_movie(reply: Mapping[str, Any]) -> dict:
    kept = {k: reply[k] for k in _MOVIE_FIELDS if k in reply}
    for field in _NAMED_FIELDS:
        if isinstance(kept.get(field), list):
            kept[field] = [{"name": item["name"]} for item in kept[field]]
    return kept


def _trim_credits(reply: Mapping[str, Any]) -> dict:
    cast = sorted(reply.get("cast", []), key=lambda member: member["order"])[:CAST]
    return {
        "cast": [
            {k: member[k] for k in ("name", "character", "order") if k in member}
            for member in cast
        ],
        "crew": [
            {"name": member["name"], "job": member["job"]}
            for member in reply.get("crew", [])
            if member.get("job") in DIRECTING | WRITING
        ],
    }


def _trim_images(reply: Mapping[str, Any]) -> dict:
    return {
        kind: [
            {k: image[k] for k in _IMAGE_FIELDS if k in image}
            for image in reply.get(kind, [])
        ]
        for kind in Images.model_fields
    }


class Tmdb(Protocol):
    def movie_ids_for_imdb(self, imdb_id: str) -> list[int]:
        """TMDB's ids of the films with this IMDb id."""
        ...

    def movie(self, tmdb_id: int) -> Movie: ...


class TmdbSidecars(Tmdb, Protocol):
    """What filing asks TMDB besides what planning does."""

    def details(self, tmdb_id: int) -> Details: ...

    def credits(self, tmdb_id: int) -> Credits: ...

    def images(self, tmdb_id: int) -> Images: ...


class Replies:
    """TMDB's replies, by the request that gave each, parsed one way."""

    def __init__(self) -> None:
        self.recorded: dict[str, dict] = {}

    def get(self, request: str) -> Mapping[str, Any]:
        raise NotImplementedError

    def movie_ids_for_imdb(self, imdb_id: str) -> list[int]:
        request = f"find/{imdb_id}"
        reply = _trim_find(self.get(request))
        self.recorded[request] = reply
        return [int(result["id"]) for result in reply["movie_results"]]

    def movie(self, tmdb_id: int) -> Movie:
        return Movie.model_validate(self.details(tmdb_id).model_dump())

    def details(self, tmdb_id: int) -> Details:
        return self._parsed(f"movie/{tmdb_id}", _trim_movie, Details)

    def credits(self, tmdb_id: int) -> Credits:
        return self._parsed(f"movie/{tmdb_id}/credits", _trim_credits, Credits)

    def images(self, tmdb_id: int) -> Images:
        return self._parsed(f"movie/{tmdb_id}/images", _trim_images, Images)

    def _parsed[T: BaseModel](self, request: str, trim, model: type[T]) -> T:
        try:
            reply = trim(self.get(request))
            self.recorded[request] = reply
            return model.model_validate(reply)
        except (ValueError, KeyError, TypeError) as error:
            raise TmdbError(f"TMDB's {request} not understood: {error}") from error


class Client(Replies):
    def __init__(
        self, token: str, transport: httpx.BaseTransport | None = None
    ) -> None:
        super().__init__()
        self._http = httpx.Client(
            base_url=API,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            params={"language": LANGUAGE},
            timeout=30.0,
            transport=transport,
        )

    def get(self, request: str) -> Mapping[str, Any]:
        params = {}
        if request.startswith("find/"):
            params["external_source"] = "imdb_id"
        if request.endswith("/images"):
            params["include_image_language"] = IMAGE_LANGUAGES
        try:
            response = self._http.get(f"/{request}", params=params)
        except httpx.HTTPError as error:
            raise TmdbError(f"TMDB's {request}: {error}") from error
        if response.status_code != 200:
            # The status alone: TMDB's message for a bad token can echo it.
            raise TmdbError(f"TMDB's {request}: HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as error:
            raise TmdbError(f"TMDB's {request} is not JSON") from error


class Recorded(Replies):
    """Replays a recording; a request it doesn't hold is a test's mistake."""

    def __init__(self, replies: Mapping[str, dict]) -> None:
        super().__init__()
        self._replies = dict(replies)

    def get(self, request: str) -> Mapping[str, Any]:
        if request not in self._replies:
            raise TmdbError(f"no recorded reply to {request}")
        return self._replies[request]


def record(client: Replies, imdb_id: str) -> dict[str, dict]:
    """Ask what identify and the sidecars ask for one film, and return the
    replies."""
    for tmdb_id in client.movie_ids_for_imdb(imdb_id):
        client.details(tmdb_id)
        client.credits(tmdb_id)
        client.images(tmdb_id)
    return dict(sorted(client.recorded.items()))


if __name__ == "__main__":
    from reelbarrow.config import Settings

    token = Settings().tmdb_token
    if token is None:
        raise SystemExit("REELBARROW_TMDB_TOKEN is not set")
    (imdb_id,) = sys.argv[1:]
    replies = record(Client(token.get_secret_value()), imdb_id)
    print(json.dumps(replies, indent=2))
