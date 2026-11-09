"""The manifest: one unit of work to file, in reelbarrow's own vocabulary.

*The manifest* in the design is the contract. This module holds what every
producer and reader of one must agree on: the schema, the file's name, the
share reference every path travels in, and the closed vocabularies the gate
branches on.
"""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath

# Raised when a field is removed or changes meaning, once reelbarrow's reader is
# deployed; a field added leaves it alone.
SCHEMA = 1
PREFIX = "manifest-"
GLOB = f"{PREFIX}*.json"


def filename(source: str, id: str) -> str:
    return f"{PREFIX}{source}-{id}.json"


class State(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class IdentityReason(StrEnum):
    SET_BY_PERSON = "set_by_person"
    LOOKUP = "lookup"
    # The value is only the disc's own name for itself, never an identity.
    NOT_IDENTIFIED = "not_identified"


class RawForm(StrEnum):
    BLURAY_BACKUP = "bluray-backup"
    DVD_IMAGE = "dvd-image"
    # A DVD's long titles as MKVs, without the disc around them.
    TITLES = "titles"


class CompleteReason(StrEnum):
    SIZES_AND_HASHES = "sizes_and_hashes"
    # Checked after the job: sizes again, but never MakeMKV's hashes.
    SIZES = "sizes"
    NOT_CHECKED = "not_checked"


class TitleReason(StrEnum):
    """Why a title has no transcode."""

    PARTS_KEPT = "parts_kept"
    WHOLE_KEPT = "whole_kept"
    SAME_AS_ANOTHER = "same_as_another"
    NOT_EXTRACTED = "not_extracted"


class ShareRefError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ShareRef:
    """A file or folder on the video share, by its path from the share's root.

    The root is the share's, not any process's mount of it: reelbarrow, ARM and
    the exporter each see a different slice at a different place, and a path in
    a manifest has to mean the same file to all of them.
    """

    path: str

    def __post_init__(self) -> None:
        path = self.path
        if not path or "\0" in path:
            raise ShareRefError(f"{path!r} is not a path")
        if path.startswith("/"):
            raise ShareRefError(f"{path!r} is absolute; it is relative to the share")
        if any(part in ("", ".", "..") for part in path.split("/")):
            raise ShareRefError(f"{path!r} has an empty, . or .. component")

    def to_json(self) -> dict[str, str]:
        return {"path": self.path}

    @classmethod
    def from_json(cls, value: object) -> "ShareRef":
        if not isinstance(value, dict) or not isinstance(value.get("path"), str):
            raise ShareRefError(f"{value!r} is not a share reference")
        return cls(value["path"])

    def resolve(self, video_root: Path) -> Path:
        """This process's path to the file. Refused if, through a symbolic link
        on the share, it lands outside the video root."""
        root = video_root.resolve()
        resolved = (root / PurePosixPath(self.path)).resolve()
        if not resolved.is_relative_to(root):
            raise ShareRefError(f"{self.path!r} resolves outside {root}")
        return resolved
