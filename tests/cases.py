"""The planner's cases: a job as intake sees it on the share, from its fixture.

A case is a folder in `fixtures/`, named for the case, holding what the
planner reads of one job (*Testing*, layer 1, in the design):

- `analysis.json`, `reelbarrow analyse`'s document of the job, captured in the
  pod and checked against a fresh listing there;
- `tmdb.json`, TMDB's replies to what identify asks, as `python -m
  reelbarrow.tmdb <imdb_id>` records them;
- `manifest.json`, the job's manifest, unless `fixtures/manifests/` holds it
  already for the exporter's tests, which is then the one copy.

The library is given by each test, since a case is planned against more than
one state of it.
"""

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from reelbarrow.analyse import Analysis
from reelbarrow.manifest import Manifest
from reelbarrow.plan import PathState
from reelbarrow.tmdb import Recorded

FIXTURES = Path(__file__).parent / "fixtures"


@dataclass(frozen=True)
class Case:
    manifest: Manifest
    analysis: Analysis
    tmdb_replies: dict[str, dict]

    @property
    def tmdb(self) -> Recorded:
        return Recorded(self.tmdb_replies)


def _manifest(folder: Path, source: str, id: str) -> Manifest:
    own = folder / "manifest.json"
    if own.exists():
        return Manifest.model_validate_json(own.read_bytes())
    for frozen in sorted((FIXTURES / "manifests").glob("*/manifest.json")):
        manifest = Manifest.model_validate_json(frozen.read_bytes())
        if (manifest.source, manifest.id) == (source, id):
            return manifest
    raise LookupError(f"no manifest for {source} {id}")


def load(name: str) -> Case:
    folder = FIXTURES / name
    analysis = Analysis.model_validate_json((folder / "analysis.json").read_bytes())
    return Case(
        manifest=_manifest(folder, analysis.source, analysis.id),
        analysis=analysis,
        tmdb_replies=json.loads((folder / "tmdb.json").read_text()),
    )


@dataclass
class Library:
    """A film library: the folders it holds, and the paths present in it."""

    folders: list[str] = field(default_factory=list)
    present: dict[str, datetime] = field(default_factory=dict)

    @classmethod
    def holding(cls, *paths: str, when: datetime) -> "Library":
        return cls(present=dict.fromkeys(paths, when))

    def movie_folders(self) -> Iterable[str]:
        return list(self.folders)

    def stat(self, path: str) -> PathState:
        if path in self.present:
            return PathState(path=path, present=True, mtime=self.present[path])
        return PathState(path=path, present=False)
