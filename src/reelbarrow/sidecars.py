"""What each sidecar a plan writes holds, rendered from its source.

A plan's `Write` names its sidecar and which record it comes from; this makes
the bytes. Everything is rendered before a plan's first operation, so a
provider that can't be reached stops the filing before anything has moved,
rather than leaving a film filed without its sidecars and nothing to add them
later. Rendering reads from TMDB and fanart.tv, and writes nothing.

The formats are *Sidecars and embedded metadata*, in the design: Kodi's NFO,
which Kodi, Jellyfin, Emby and tinyMediaManager all read, and artwork at Kodi's
names. An artwork that neither provider has is not written, and says so.
"""

import json
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Protocol
from urllib.parse import urlsplit

import httpx

from reelbarrow import fanart, tmdb
from reelbarrow.plan import Sidecar, Write

TMDB_IMAGES = "https://image.tmdb.org/t/p/original"
# The only hosts artwork is fetched from: what TMDB and fanart.tv link to.
IMAGE_HOSTS = frozenset({"image.tmdb.org", "assets.fanart.tv"})
# Larger than any poster or 4K backdrop either provider serves.
MAX_IMAGE_BYTES = 50 * 1024 * 1024
# What a file's first bytes are, by the format its name says.
MAGIC = {".jpg": b"\xff\xd8\xff", ".png": b"\x89PNG\r\n\x1a\n"}
# fanart.tv's language for art with no text on it.
NO_TEXT = frozenset({"00", ""})


class SidecarError(Exception):
    """A sidecar can't be rendered as the plan says, so nothing is filed."""


class ImageFetcher(Protocol):
    def fetch(self, url: str) -> bytes | None:
        """The image's bytes, or None where its provider no longer has it."""
        ...


class HttpImages:
    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self._http = httpx.Client(timeout=60.0, transport=transport)

    def fetch(self, url: str) -> bytes | None:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or parts.hostname not in IMAGE_HOSTS:
            raise SidecarError(f"{url} isn't on an artwork host")
        # fanart.tv has linked its art over plain HTTP; both hosts serve HTTPS.
        url = parts._replace(scheme="https").geturl()
        try:
            with self._http.stream("GET", url) as response:
                if response.status_code == 404:
                    return None
                if response.status_code != 200:
                    raise SidecarError(f"{url}: HTTP {response.status_code}")
                content = bytearray()
                for chunk in response.iter_bytes():
                    content += chunk
                    if len(content) > MAX_IMAGE_BYTES:
                        raise SidecarError(f"{url} is larger than any artwork")
                return bytes(content)
        except httpx.HTTPError as error:
            raise SidecarError(f"{url}: {error}") from error


@dataclass(frozen=True)
class Candidate:
    url: str
    source: str


@dataclass
class Sources:
    tmdb: tmdb.TmdbSidecars
    fanart: fanart.Fanart
    images: ImageFetcher
    # One reply per film, however many sidecars read it.
    _fanart: dict[int, fanart.MovieArt] = field(default_factory=dict)
    _images: dict[int, tmdb.Images] = field(default_factory=dict)

    def fanart_movie(self, tmdb_id: int) -> fanart.MovieArt:
        if tmdb_id not in self._fanart:
            self._fanart[tmdb_id] = self.fanart.movie(tmdb_id)
        return self._fanart[tmdb_id]

    def tmdb_images(self, tmdb_id: int) -> tmdb.Images:
        if tmdb_id not in self._images:
            self._images[tmdb_id] = self.tmdb.images(tmdb_id)
        return self._images[tmdb_id]


@dataclass(frozen=True)
class Rendered:
    # None: nothing to write, and the detail says why.
    content: bytes | None
    detail: str


def render(write: Write, sources: Sources) -> Rendered:
    match write.sidecar:
        case Sidecar.IGNORE_MARKER:
            return Rendered(b"", "an empty marker")
        case Sidecar.DISC_JSON:
            if write.content is None:
                raise SidecarError(f"{write.path}: no document to write")
            text = json.dumps(write.content, indent=2, ensure_ascii=False) + "\n"
            return Rendered(text.encode(), "the plan's document")
        case Sidecar.MOVIE_NFO:
            return _movie_nfo(write, sources)
        case Sidecar.ARTWORK:
            return _artwork(write, sources)
    raise SidecarError(f"{write.path}: no renderer for {write.sidecar}")


def _field(write: Write, name: str) -> object:
    if not write.content or name not in write.content:
        raise SidecarError(f"{write.path}: the plan names no {name}")
    return write.content[name]


def _movie_nfo(write: Write, sources: Sources) -> Rendered:
    tmdb_id = _field(write, "tmdb_id")
    imdb_id = _field(write, "imdb_id")
    if not isinstance(tmdb_id, int):
        raise SidecarError(f"{write.path}: TMDB id {tmdb_id!r}")
    details = sources.tmdb.details(tmdb_id)
    if imdb_id is not None and details.imdb_id != imdb_id:
        raise SidecarError(
            f"TMDB {tmdb_id} is now {details.imdb_id}, not {imdb_id} as planned"
        )
    credits = sources.tmdb.credits(tmdb_id)
    return Rendered(
        movie_nfo(details, credits, imdb_id if isinstance(imdb_id, str) else None),
        f"TMDB {tmdb_id}'s record",
    )


def _unique(names: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(names))


def movie_nfo(
    details: tmdb.Details, credits: tmdb.Credits, imdb_id: str | None
) -> bytes:
    """Kodi's movie.nfo, in the order Kodi's own writer uses."""
    movie = ET.Element("movie")

    def add(tag: str, text: object, **attributes: str) -> ET.Element:
        element = ET.SubElement(movie, tag, attributes)
        element.text = str(text)
        return element

    add("title", details.title)
    if details.original_title:
        add("originaltitle", details.original_title)
    if details.overview:
        add("plot", details.overview)
    if details.tagline:
        add("tagline", details.tagline)
    if details.runtime:
        add("runtime", details.runtime)
    add("uniqueid", details.id, type="tmdb", default="true")
    if imdb_id:
        add("uniqueid", imdb_id, type="imdb")
    for genre in details.genres:
        add("genre", genre.name)
    for country in details.production_countries:
        add("country", country.name)
    for writer in _unique(m.name for m in credits.crew if m.job in tmdb.WRITING):
        add("credits", writer)
    for director in _unique(m.name for m in credits.crew if m.job in tmdb.DIRECTING):
        add("director", director)
    if details.release_date:
        add("premiered", details.release_date)
    if details.year is not None:
        add("year", details.year)
    for studio in details.production_companies:
        add("studio", studio.name)
    for member in sorted(credits.cast, key=lambda m: m.order):
        actor = ET.SubElement(movie, "actor")
        ET.SubElement(actor, "name").text = member.name
        if member.character:
            ET.SubElement(actor, "role").text = member.character
        ET.SubElement(actor, "order").text = str(member.order)
    ET.indent(movie, space="  ")
    return ET.tostring(movie, encoding="UTF-8", xml_declaration=True) + b"\n"


def _tmdb(images: Iterable[tmdb.Image], *languages: str | None) -> list[Candidate]:
    ranked = sorted(images, key=lambda i: (-i.vote_average, -i.vote_count))
    return [
        Candidate(f"{TMDB_IMAGES}{image.file_path}", f"TMDB's {image.file_path}")
        for language in languages
        for image in ranked
        if image.iso_639_1 == language
    ]


def _fanart(art: Iterable[fanart.Art], *languages: frozenset[str]) -> list[Candidate]:
    ranked = sorted(art, key=lambda a: -a.likes)
    return [
        Candidate(a.url, f"fanart.tv's {PurePosixPath(urlsplit(a.url).path).name}")
        for language in languages
        for a in ranked
        if a.lang in language
    ]


EN = frozenset({"en"})

# Each artwork's candidates, best first: English, or no text where the art is
# a picture rather than a title. Art in another language is never used.
CANDIDATES: dict[str, Callable[[tmdb.Images, fanart.MovieArt], list[Candidate]]] = {
    "poster": lambda t, f: (
        _tmdb(t.posters, "en", None) + _fanart(f.movieposter, EN, NO_TEXT)
    ),
    "fanart": lambda t, f: (
        _tmdb(t.backdrops, None, "en") + _fanart(f.moviebackground, NO_TEXT, EN)
    ),
    "clearlogo": lambda t, f: (
        _fanart(f.hdmovielogo, EN)
        + [c for c in _tmdb(t.logos, "en") if c.url.endswith(".png")]
    ),
    "clearart": lambda t, f: _fanart(f.hdmovieclearart, EN, NO_TEXT),
    "landscape": lambda t, f: _fanart(f.moviethumb, EN, NO_TEXT),
    "disc": lambda t, f: _fanart(f.moviedisc, EN, NO_TEXT),
}


def _artwork(write: Write, sources: Sources) -> Rendered:
    tmdb_id = _field(write, "tmdb_id")
    kind = _field(write, "kind")
    suffix = PurePosixPath(write.path).suffix.lower()
    if not isinstance(tmdb_id, int) or kind not in CANDIDATES or suffix not in MAGIC:
        raise SidecarError(f"{write.path}: no artwork {kind!r} for TMDB {tmdb_id!r}")
    candidates = CANDIDATES[str(kind)](
        sources.tmdb_images(tmdb_id), sources.fanart_movie(tmdb_id)
    )
    passed = []
    for candidate in candidates:
        content = sources.images.fetch(candidate.url)
        if content is None:
            passed.append(f"{candidate.source} is gone")
        elif not content.startswith(MAGIC[suffix]):
            passed.append(f"{candidate.source} isn't a {suffix}")
        else:
            return Rendered(content, f"{candidate.source}, {len(content):,} bytes")
    return Rendered(
        None,
        f"neither TMDB nor fanart.tv has a {kind}"
        + (f": {'; '.join(passed)}" if passed else ""),
    )
