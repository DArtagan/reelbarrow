import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from reelbarrow.analysis.tools import AnalysisError

# The navigation files: equal across every backup of one disc, complete or not.
# CERTIFICATE/id.bdmv is deliberately absent. It sits outside BDMV/, and three
# different Dark Knight bonus discs share one.
NAV_FILES = ("BDMV/index.bdmv", "BDMV/MovieObject.bdmv")
NAV_DIR = "BDMV/PLAYLIST/"


@dataclass(frozen=True, slots=True)
class BlurayHashes:
    # SHA-1 over the path and bytes of each navigation file: the disc's identity.
    nav: str
    # SHA-1 over the path and size of every file under BDMV/: equal only for
    # copies holding the same files.
    completeness: str
    files: int
    bytes: int


def bluray_hashes(root: Path) -> BlurayHashes:
    """Hash a raw Blu-ray copy, given the directory that holds its BDMV/."""
    if not (root / "BDMV").is_dir():
        raise AnalysisError(f"{root} has no BDMV directory")

    nav = hashlib.sha1()
    entries = []
    total = 0
    # Directories in sorted order, each one's files before its subdirectories,
    # so the hashes do not depend on the order the filesystem lists them in.
    for dirpath, dirnames, filenames in os.walk(root / "BDMV"):
        dirnames.sort()
        for name in sorted(filenames):
            path = Path(dirpath, name)
            relative = path.relative_to(root).as_posix()
            size = path.stat().st_size
            entries.append(f"{relative}:{size}")
            total += size
            if relative in NAV_FILES or relative.startswith(NAV_DIR):
                nav.update(os.fsencode(relative))
                nav.update(path.read_bytes())

    completeness = hashlib.sha1(os.fsencode("\n".join(entries))).hexdigest()
    return BlurayHashes(nav.hexdigest(), completeness, len(entries), total)
