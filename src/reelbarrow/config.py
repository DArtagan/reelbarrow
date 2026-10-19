from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REELBARROW_")

    # True unless the deployment says otherwise: a missing or misspelt variable
    # must leave the share untouched, never start moving files.
    dry_run: bool = True

    # Root of the video share: holds both import/ and the movies/ and shows/
    # libraries, which must be one filesystem for filing to be a rename().
    video_root: Path = Path("/video")
    # Where ARM's hook writes manifests/job-<id>.json.
    manifest_dir: Path = Path("/video/import/automatic-ripping-machine/manifests")
    # Job state and the ledger.
    data_dir: Path = Path("/data")
