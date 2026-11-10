"""fanart.tv, for the artwork TMDB doesn't keep: logos, clear art, disc art and
landscape thumbs.

As with TMDB (`reelbarrow.tmdb`), only the fields a sidecar reads are kept from
its replies, and a fixture records those replies trimmed, in fanart.tv's own
shape. `python -m reelbarrow.fanart <tmdb_id>` prints such a recording, made
with the key in the environment.
"""

import json
import sys
from collections.abc import Mapping
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, field_validator

# v3.2 is v3 with image sizes added; the fields read here are v3's.
API = "https://webservice.fanart.tv/v3.2"


class FanartError(Exception):
    """fanart.tv could not be asked, or gave a reply that isn't understood."""


class Art(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    url: str
    # Two letters, or "00" (or empty) for art with no text on it.
    lang: str = ""
    likes: int = 0

    @field_validator("likes", mode="before")
    @classmethod
    def _counted(cls, value: object) -> object:
        # fanart.tv sends its counts as strings.
        return int(value) if isinstance(value, str) and value.isdigit() else value


class MovieArt(BaseModel):
    """A film's art on fanart.tv, by its kinds there. Empty: it has none."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    movieposter: list[Art] = []
    moviebackground: list[Art] = []
    hdmovielogo: list[Art] = []
    hdmovieclearart: list[Art] = []
    moviethumb: list[Art] = []
    moviedisc: list[Art] = []


_ART_FIELDS = tuple(Art.model_fields)


def _trim(reply: Mapping[str, Any]) -> dict:
    return {
        kind: [{k: art[k] for k in _ART_FIELDS if k in art} for art in reply[kind]]
        for kind in MovieArt.model_fields
        if isinstance(reply.get(kind), list)
    }


class Fanart(Protocol):
    def movie(self, tmdb_id: int) -> MovieArt: ...


class Replies:
    """fanart.tv's replies, by the request that gave each, parsed one way."""

    def __init__(self) -> None:
        self.recorded: dict[str, dict] = {}

    def get(self, request: str) -> Mapping[str, Any] | None:
        """The reply, or None where fanart.tv has nothing for it."""
        raise NotImplementedError

    def movie(self, tmdb_id: int) -> MovieArt:
        request = f"movies/{tmdb_id}"
        reply = self.get(request)
        trimmed = {} if reply is None else _trim(reply)
        self.recorded[request] = trimmed
        try:
            return MovieArt.model_validate(trimmed)
        except ValueError as error:
            raise FanartError(
                f"fanart.tv's {request} not understood: {error}"
            ) from error


class Client(Replies):
    def __init__(self, key: str, transport: httpx.BaseTransport | None = None) -> None:
        super().__init__()
        # A header rather than the `api_key` parameter, so the key never
        # appears in a URL that might be logged.
        self._http = httpx.Client(
            base_url=API,
            headers={"api-key": key, "Accept": "application/json"},
            timeout=30.0,
            transport=transport,
        )

    def get(self, request: str) -> Mapping[str, Any] | None:
        try:
            response = self._http.get(f"/{request}")
        except httpx.HTTPError as error:
            raise FanartError(f"fanart.tv's {request}: {error}") from error
        # What fanart.tv answers for a film it holds no art for.
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise FanartError(f"fanart.tv's {request}: HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as error:
            raise FanartError(f"fanart.tv's {request} is not JSON") from error


class Recorded(Replies):
    """Replays a recording; a request it doesn't hold is a test's mistake."""

    def __init__(self, replies: Mapping[str, dict]) -> None:
        super().__init__()
        self._replies = dict(replies)

    def get(self, request: str) -> Mapping[str, Any] | None:
        if request not in self._replies:
            raise FanartError(f"no recorded reply to {request}")
        return self._replies[request]


def record(client: Replies, tmdb_id: int) -> dict[str, dict]:
    client.movie(tmdb_id)
    return dict(sorted(client.recorded.items()))


if __name__ == "__main__":
    from reelbarrow.config import Settings

    key = Settings().fanart_key
    if key is None:
        raise SystemExit("REELBARROW_FANART_KEY is not set")
    (tmdb_id,) = sys.argv[1:]
    print(json.dumps(record(Client(key.get_secret_value()), int(tmdb_id)), indent=2))
