"""TMDB, for what a film is called and how long it runs.

Only the fields a rule reads are kept from TMDB's replies, and a fixture
records those replies in TMDB's own shape, trimmed, so the tests replay
exactly what the service would have parsed. `python -m reelbarrow.tmdb
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


# What is kept of each reply, so a recording holds what a rule reads.
_FIND_FIELDS = ("id",)
_MOVIE_FIELDS = tuple(Movie.model_fields)


def _trim_find(reply: Mapping[str, Any]) -> dict:
    return {
        "movie_results": [
            {k: r[k] for k in _FIND_FIELDS if k in r}
            for r in reply.get("movie_results", [])
        ]
    }


def _trim_movie(reply: Mapping[str, Any]) -> dict:
    return {k: reply[k] for k in _MOVIE_FIELDS if k in reply}


class Tmdb(Protocol):
    def movies_for_imdb(self, imdb_id: str) -> list[int]:
        """TMDB's ids of the films with this IMDb id."""
        ...

    def movie(self, tmdb_id: int) -> Movie: ...


class Replies:
    """TMDB's replies, by the request that gave each, parsed one way."""

    def __init__(self) -> None:
        self.recorded: dict[str, dict] = {}

    def get(self, request: str) -> Mapping[str, Any]:
        raise NotImplementedError

    def movies_for_imdb(self, imdb_id: str) -> list[int]:
        request = f"find/{imdb_id}"
        reply = _trim_find(self.get(request))
        self.recorded[request] = reply
        return [int(result["id"]) for result in reply["movie_results"]]

    def movie(self, tmdb_id: int) -> Movie:
        request = f"movie/{tmdb_id}"
        reply = _trim_movie(self.get(request))
        self.recorded[request] = reply
        try:
            return Movie.model_validate(reply)
        except ValueError as error:
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
        params = {"external_source": "imdb_id"} if request.startswith("find/") else {}
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
    """Ask what identify asks for one film, and return the replies."""
    for tmdb_id in client.movies_for_imdb(imdb_id):
        client.movie(tmdb_id)
    return dict(sorted(client.recorded.items()))


if __name__ == "__main__":
    from reelbarrow.config import Settings

    token = Settings().tmdb_token
    if token is None:
        raise SystemExit("REELBARROW_TMDB_TOKEN is not set")
    (imdb_id,) = sys.argv[1:]
    replies = record(Client(token.get_secret_value()), imdb_id)
    print(json.dumps(replies, indent=2))
