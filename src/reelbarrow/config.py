import json
from pathlib import Path
from typing import Annotated

from pydantic import AnyHttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REELBARROW_")

    # True unless the deployment says otherwise: a missing or misspelt variable
    # must leave the share untouched, never start moving files.
    dry_run: bool = True

    # Root of the video share: holds both import/ and the movies/ and shows/
    # libraries, which must be one filesystem for filing to be a rename().
    video_root: Path = Path("/video")
    # Where the exporter (`reelbarrow arm-export-manifests`) writes ARM's
    # manifests, one a job.
    manifest_dir: Path = Path("/video/import/automatic-ripping-machine/manifests")
    # Job state and the ledger.
    data_dir: Path = Path("/data")

    # The share's paths, from video_root, as a manifest's are. Where ARM puts
    # its raw copies: intake looks here for a job's when its manifest records
    # none.
    arm_raw: str = "import/automatic-ripping-machine/raw"
    # The film library Plex reads.
    movies: str = "movies"

    # TMDB's API Read Access Token, sent as a bearer header so it never
    # appears in a URL that might be logged.
    tmdb_token: SecretStr | None = None
    # fanart.tv's personal API key, sent as a header for the same reason.
    fanart_key: SecretStr | None = None

    # Plex, told to scan each folder filing touched. Its paths are where its
    # own container mounts each library, by the library's path on the share,
    # as JSON: {"movies": "/data/movies"}.
    plex_url: AnyHttpUrl | None = None
    plex_token: SecretStr | None = None
    plex_paths: Annotated[dict[str, str], NoDecode] = {}

    @field_validator(
        "tmdb_token", "fanart_key", "plex_token", "plex_url", mode="before"
    )
    @classmethod
    def _empty_is_unset(cls, value: object) -> object:
        # compose.yaml passes an unset variable on as an empty string.
        return None if value == "" else value

    @field_validator("plex_paths", mode="before")
    @classmethod
    def _json(cls, value: object) -> object:
        # Decoded here rather than by the settings source, so that an empty
        # string is unset too.
        if isinstance(value, str):
            return json.loads(value) if value.strip() else {}
        return value
