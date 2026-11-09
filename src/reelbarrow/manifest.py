"""The manifest: one unit of work to file, in reelbarrow's own vocabulary.

*The manifest* in the design is the contract, and these models are its
machine-checkable form: a producer builds one, so every manifest is validated
as it is written, and intake parses with them. `docs/manifest.schema.json` is
generated from them (`python -m reelbarrow.manifest`), for producers that
aren't Python.

A field left out was not recorded; a field that is null records that there is
none. Models are built from what was recorded and dumped with
`exclude_unset`, so the two never blur.
"""

import json
import re
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Annotated, ClassVar, Literal, Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)
from pydantic.json_schema import SkipJsonSchema

# Raised when a field is removed or changes meaning, once reelbarrow's reader is
# deployed; a field added leaves it alone.
SCHEMA = 1
PREFIX = "manifest-"
GLOB = f"{PREFIX}*.json"
SCHEMA_FILE = Path(__file__).parents[2] / "docs" / "manifest.schema.json"

# For a field that may be left out but is never null.
Absent = SkipJsonSchema[None]


def filename(source: str, id: str) -> str:
    return f"{PREFIX}{source}-{id}.json"


class State(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class IdentityReason(StrEnum):
    SET_BY_PERSON = "set_by_person"
    LOOKUP = "lookup"
    # The producer took it from an earlier unit of work it matched only by the
    # disc's label, which discs share.
    COPIED_FROM_EARLIER_JOB = "copied_from_earlier_job"
    # The value is only the disc's own name for itself, never an identity.
    NOT_IDENTIFIED = "not_identified"


class RawForm(StrEnum):
    BLURAY_BACKUP = "bluray-backup"
    DVD_IMAGE = "dvd-image"
    # A DVD's long titles as MKVs, without the disc around them.
    MKV_TITLES = "mkv-titles"


class CheckState(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    NOT_RUN = "not_run"


class TitleReason(StrEnum):
    """Why a title has no transcode."""

    # Titles that were transcoded already play it; the manifest says which.
    PLAYED_BY_KEPT_TITLES = "played_by_kept_titles"
    # A DVD title MakeMKV listed and didn't save.
    NOT_EXTRACTED = "not_extracted"


class Model(BaseModel):
    # A reader ignores fields it doesn't know.
    model_config = ConfigDict(extra="ignore", frozen=True)
    # Fields that may be left out but are never null.
    never_null: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def _absent_not_null(self) -> Self:
        for name in self.never_null & self.model_fields_set:
            if getattr(self, name) is None:
                raise ValueError(f"{name} is left out when not recorded, never null")
        return self


class ShareRef(Model):
    """A file or folder on the video share, by its path from the share's root.

    The root is the share's, not any process's mount of it: reelbarrow, ARM and
    the exporter each see a different slice at a different place, and a path in
    a manifest has to mean the same file to all of them.
    """

    path: str = Field(
        description="From the share's root: `/` separators, no leading `/`, no "
        "`.` or `..`, the name exactly as on the share."
    )

    @field_validator("path")
    @classmethod
    def _plain(cls, path: str) -> str:
        if not path or "\0" in path:
            raise ValueError(f"{path!r} is not a path")
        if path.startswith("/"):
            raise ValueError(f"{path!r} is absolute; it is relative to the share")
        if any(part in ("", ".", "..") for part in path.split("/")):
            raise ValueError(f"{path!r} has an empty, . or .. component")
        return path

    def resolve(self, video_root: Path) -> Path:
        """This process's path to the file. Refused if, through a symbolic link
        on the share, it lands outside the video root."""
        root = video_root.resolve()
        resolved = (root / PurePosixPath(self.path)).resolve()
        if not resolved.is_relative_to(root):
            raise ValueError(f"{self.path!r} resolves outside {root}")
        return resolved


class Claim(Model):
    value: str | None
    reason: IdentityReason


class KindClaim(Claim):
    value: Literal["movie", "series"] | None


class Identity(Model):
    """What the work is, each field with who supplied it."""

    title: Claim
    year: Claim
    imdb_id: Claim
    kind: KindClaim


class Disc(Model):
    type: str | None = None
    label: str | None = None
    crc64: Annotated[str, Field(pattern=r"^[0-9a-f]{16}$")] | None = Field(
        default=None, description="A DVD's pydvdid CRC64; null for any other disc."
    )


class Completed(Model):
    folder: ShareRef


class Check(Model):
    """The backup's two checks. The copy is whole when both passed."""

    sizes: CheckState = Field(
        description="Every file against the disc's own record of its size."
    )
    hashes: CheckState = Field(
        description="MakeMKV's check of each file against the disc's hashes, as "
        "it copied. Never rerun, so `not_run` on a copy checked afterwards."
    )

    @property
    def whole(self) -> bool:
        return self.sizes is self.hashes is CheckState.PASSED


class Raw(Model):
    never_null = frozenset({"image", "titles_compared"})

    form: RawForm
    folder: ShareRef
    image: ShareRef | Absent = None
    check: Check
    problems: list[str] = Field(description="Each check's failures.")
    titles_compared: Literal[True] | Absent = Field(
        default=None,
        description="The titles were compared for those that repeat others, so "
        "a title that is no whole and has no reason repeats nothing. Left out: "
        "they weren't, and nothing is known either way.",
    )

    @model_validator(mode="after")
    def _image_is_an_images(self) -> Self:
        if self.image is not None and self.form is not RawForm.DVD_IMAGE:
            raise ValueError(f"a {self.form} has no image")
        failed = CheckState.FAILED in (self.check.sizes, self.check.hashes)
        if failed != bool(self.problems):
            raise ValueError("problems are listed exactly when a check failed")
        return self


class DiscKey(Model):
    """A title by the disc's own number for it: a DVD's title number, which
    opens it in the image, or a Blu-ray's playlist."""

    never_null = frozenset({"disc_title", "playlist"})

    disc_title: Annotated[int, Field(ge=1)] | Absent = None
    playlist: Annotated[str, Field(pattern=r"(?i)^\d{5}\.mpls$")] | Absent = None

    @property
    def key(self) -> int | str:
        return self.disc_title if self.disc_title is not None else self.playlist

    @model_validator(mode="after")
    def _one_key(self) -> Self:
        if (self.disc_title is None) == (self.playlist is None):
            raise ValueError("a title has a disc_title or a playlist, not both")
        return self


class Part(DiscKey):
    start: float = Field(
        ge=0,
        description="The second of the whole at which the part begins, in the "
        "playback time its transcode's chapters keep.",
    )


class Title(DiscKey):
    never_null = DiscKey.never_null | {
        "extracted",
        "played_by",
        "interleaved",
        "parts",
    }

    extracted: ShareRef | Absent = Field(
        default=None, description="A DVD title's MKV, extracted from the image."
    )
    transcode: ShareRef | None = Field(
        default=None,
        description="Where the producer put its transcode. Null: none, and "
        "`reason` says why. Left out: not recorded.",
    )
    reason: TitleReason | None = None
    played_by: DiscKey | Absent = Field(
        default=None,
        description="The title kept that plays this one, where its own `parts` "
        "or a whole it is a part of don't say so: a copy, a shuffle, a title "
        "inside a whole.",
    )
    interleaved: bool | Absent = Field(
        default=None, description="A whole's parts are cut into one another."
    )
    parts: list[Part] | Absent = Field(
        default=None,
        min_length=2,
        description="A whole's: the disjoint titles that play it between them, "
        "in order.",
    )

    @model_validator(mode="after")
    def _reason_for_no_transcode(self) -> Self:
        if "transcode" not in self.model_fields_set:
            if "reason" in self.model_fields_set:
                raise ValueError("a reason without a transcode recorded")
        elif (self.transcode is None) != (self.reason is not None):
            raise ValueError("a reason exactly when there is no transcode")
        if (self.parts is None) != (self.interleaved is None):
            raise ValueError("a whole has both parts and interleaved")
        if self.played_by is not None and self.reason is not (
            TitleReason.PLAYED_BY_KEPT_TITLES
        ):
            raise ValueError("played_by on a title not played by kept titles")
        if self.reason is TitleReason.NOT_EXTRACTED and self.extracted is not None:
            raise ValueError("an extracted title that wasn't extracted")
        return self


class Manifest(Model):
    """One unit of work to file. *The manifest*, in reelbarrow's design."""

    never_null = frozenset({"disc", "identity", "raw", "titles"})

    schema_: Literal[1] = Field(alias="schema")
    source: Annotated[str, Field(pattern=r"^[a-z0-9]+$")]
    id: Annotated[str, Field(pattern=r"^[A-Za-z0-9._-]+$")] = Field(
        description="Unique within its source; ARM's is `<job_id>-<stage>`."
    )
    state: State
    start_time: AwareDatetime | None = None
    finish_time: AwareDatetime | None = None
    errors: str | None = None
    disc: Disc | Absent = None
    identity: Identity | Absent = None
    completed: Completed | None = Field(
        default=None, description="Null: the producer made no output folder."
    )
    raw: Raw | Absent = Field(default=None, description="Left out: not recorded.")
    titles: list[Title] | Absent = Field(
        default=None,
        description="Each title from the disc to its transcode, keyed by the "
        "disc's own number for it. Left out: not recorded.",
    )

    model_config = ConfigDict(
        extra="ignore",
        frozen=True,
        populate_by_name=True,
        title="reelbarrow manifest",
    )

    @model_validator(mode="after")
    def _titles_account_for_each_other(self) -> Self:
        """Every title played by kept titles says by which, once: its own
        `parts`, a whole it is a part of, or `played_by`. What it names may be
        played by others in turn, as a shuffle of a play-all is by the play-all's
        episodes, so long as each chain ends in titles kept."""
        if self.titles is None:
            return self
        if self.raw is None:
            raise ValueError("titles without the raw copy they are on")
        titles = {title.key: title for title in self.titles}
        if len(titles) != len(self.titles):
            raise ValueError("two titles with one disc number")
        kept = {key for key, title in titles.items() if title.reason is None}
        inside: dict[int | str, list] = {}
        for title in self.titles:
            for part in title.parts or []:
                if part.key not in titles:
                    raise ValueError(f"{title.key}'s part {part.key} is no title")
                inside.setdefault(part.key, []).append(title.key)
        played: dict[int | str, list[int | str]] = {}
        for key, title in titles.items():
            if (
                title.parts is not None or key in inside
            ) and not self.raw.titles_compared:
                raise ValueError("wholes, though the titles weren't compared")
            if title.reason is not TitleReason.PLAYED_BY_KEPT_TITLES:
                continue
            if not self.raw.titles_compared:
                raise ValueError(f"{key} played by others, though none compared")
            structure = title.parts is not None or key in inside
            if title.played_by is None and not structure:
                raise ValueError(f"nothing says what plays {key}")
            if title.played_by is not None and structure:
                raise ValueError(f"{key}'s played_by repeats what its whole says")
            if title.played_by is not None and title.played_by.key not in titles:
                raise ValueError(f"{key} is played by {title.played_by.key}, no title")
            # Each way it could be played: by all its parts, by a whole it's
            # in, or by the title it repeats.
            played[key] = [title.played_by.key] if title.played_by else []
        accounted = set(kept)
        pending = set(played)
        while pending:
            settled = {
                key
                for key in pending
                if any(p in accounted for p in played[key])
                or any(whole in accounted for whole in inside.get(key, []))
                or (
                    titles[key].parts is not None
                    and all(p.key in accounted for p in titles[key].parts)
                )
            }
            if not settled:
                raise ValueError(f"nothing kept plays {sorted(pending, key=str)}")
            accounted |= settled
            pending -= settled
        return self

    def to_json(self) -> dict:
        return self.model_dump(mode="json", by_alias=True, exclude_unset=True)


def schema() -> dict:
    """The manifest's JSON Schema, as `docs/manifest.schema.json` holds it."""
    document = Manifest.model_json_schema(by_alias=True, mode="validation")
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://github.com/DArtagan/reelbarrow/blob/main/docs/manifest.schema.json",
        **document,
    }


def write_schema() -> None:
    SCHEMA_FILE.write_text(json.dumps(schema(), indent=2) + "\n")


if __name__ == "__main__":
    write_schema()
    print(re.sub(r"^.*?docs/", "docs/", str(SCHEMA_FILE)))
