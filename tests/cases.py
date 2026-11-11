"""The planner's cases: a job as intake sees it on the share, from its fixture.

A case is a folder in `fixtures/`, named for the case, holding what the
planner reads of one job (*Testing*, layer 1, in the design):

- `analysis.json`, `reelbarrow analyse`'s document of the job, captured in the
  pod and checked against a fresh listing there;
- `tmdb.json`, TMDB's replies to what identify and the sidecars ask, as
  `python -m reelbarrow.tmdb <imdb_id>` records them;
- `fanart.json`, fanart.tv's replies for the artwork, as `python -m
  reelbarrow.fanart <tmdb_id>` records them;
- `manifest.json`, the job's manifest, unless `fixtures/manifests/` holds it
  already for the exporter's tests, which is then the one copy.

The library is given by each test, since a case is planned against more than
one state of it. `Case.build` lays the job's files out on a synthetic share
for the executor to carry its plan out on.
"""

import json
import os
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PurePosixPath

from reelbarrow.analyse import Analysis, Entry
from reelbarrow.manifest import Manifest
from reelbarrow.plan import PathState
from reelbarrow.tmdb import Recorded

FIXTURES = Path(__file__).parent / "fixtures"


@dataclass(frozen=True)
class Case:
    manifest: Manifest
    analysis: Analysis
    tmdb_replies: dict[str, dict]
    fanart_replies: dict[str, dict]

    @property
    def tmdb(self) -> Recorded:
        return Recorded(self.tmdb_replies)

    def build(self, root: Path) -> None:
        """The job's folders and files under a share's root, as the analysis
        measured them: each file sparse, at its size, and every entry at its
        modification time, so the plan's basis matches the tree exactly. The
        files hold no media; nothing here reads them."""
        folders = [self.analysis.completed] if self.analysis.completed else []
        folders += self.analysis.raw
        entries: list[Entry] = []
        for folder in folders:
            (root / folder.path).mkdir(parents=True)
            entries.append(folder)
            for under in folder.folders:
                (root / under.path).mkdir(parents=True, exist_ok=True)
                entries.append(under)
            for file in folder.files:
                with open(root / file.path, "wb") as made:
                    made.truncate(file.size)
                entries.append(file)
        # Deepest first, so a folder's time is set after what is made in it.
        for entry in sorted(entries, key=lambda e: -len(PurePosixPath(e.path).parts)):
            ns = _ns(entry.mtime)
            os.utime(root / entry.path, ns=(ns, ns))


def _manifest(folder: Path, source: str, id: str) -> Manifest:
    own = folder / "manifest.json"
    if own.exists():
        return Manifest.model_validate_json(own.read_bytes())
    for frozen in sorted((FIXTURES / "manifests").glob("*/manifest.json")):
        manifest = Manifest.model_validate_json(frozen.read_bytes())
        if (manifest.source, manifest.id) == (source, id):
            return manifest
    raise LookupError(f"no manifest for {source} {id}")


def _ns(when: datetime) -> int:
    # Exact, where a float timestamp would round the microseconds.
    delta = when - datetime.fromtimestamp(0, when.tzinfo)
    return (delta.days * 86_400 + delta.seconds) * 10**9 + delta.microseconds * 1000


def load(name: str, fixtures: Path = FIXTURES) -> Case:
    folder = fixtures / name
    analysis = Analysis.model_validate_json((folder / "analysis.json").read_bytes())
    fanart = folder / "fanart.json"
    return Case(
        manifest=_manifest(folder, analysis.source, analysis.id),
        analysis=analysis,
        tmdb_replies=json.loads((folder / "tmdb.json").read_text()),
        fanart_replies=json.loads(fanart.read_text()) if fanart.exists() else {},
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
