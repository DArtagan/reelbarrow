"""Plex, told to scan the folders filing touched.

Plex's own change detection can't be relied on over the share's CIFS mount, so
each filing ends with a partial scan of the film's folder
(`/library/sections/{id}/refresh?path=…`). Plex mounts each library at a path
of its own, which the share's path is translated to; the section is the one
whose location holds that path, read from Plex rather than configured, so a
section recreated in Plex needs no change here.
"""

from collections.abc import Mapping
from pathlib import PurePosixPath

import httpx


class PlexError(Exception):
    """Plex could not be asked, or doesn't hold the folder."""


class Plex:
    def __init__(
        self,
        url: str,
        token: str,
        paths: Mapping[str, str],
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.paths = dict(paths)
        # A header rather than the X-Plex-Token parameter, so the token never
        # appears in a URL that might be logged.
        self._http = httpx.Client(
            base_url=url,
            headers={"X-Plex-Token": token, "Accept": "application/json"},
            timeout=30.0,
            transport=transport,
        )

    def path(self, share_path: str) -> str:
        """Plex's path to a folder on the share."""
        for library, mounted in sorted(self.paths.items(), key=lambda p: -len(p[0])):
            if share_path == library or share_path.startswith(f"{library}/"):
                rest = share_path[len(library) :].lstrip("/")
                return str(PurePosixPath(mounted) / rest) if rest else mounted
        raise PlexError(f"{share_path} isn't in a library Plex mounts")

    def scan(self, share_path: str) -> str:
        """Scan one folder; says which section scanned it."""
        path = self.path(share_path)
        section = self._section(path)
        self._get(f"/library/sections/{section}/refresh", {"path": path})
        return f"section {section} scanning {path}"

    def _section(self, path: str) -> str:
        reply = self._get("/library/sections", {})
        try:
            directories = reply["MediaContainer"].get("Directory", [])
            holding = [
                str(directory["key"])
                for directory in directories
                for location in directory.get("Location", [])
                if PurePosixPath(path).is_relative_to(location["path"])
            ]
        except (KeyError, TypeError, AttributeError) as error:
            raise PlexError(f"Plex's sections not understood: {error!r}") from error
        if len(holding) != 1:
            raise PlexError(f"{len(holding)} of Plex's sections hold {path}")
        return holding[0]

    def _get(self, request: str, params: Mapping[str, str]) -> dict:
        try:
            response = self._http.get(request, params=params)
        except httpx.HTTPError as error:
            raise PlexError(f"Plex's {request}: {error}") from error
        if response.status_code != 200:
            raise PlexError(f"Plex's {request}: HTTP {response.status_code}")
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError as error:
            raise PlexError(f"Plex's {request} is not JSON") from error
