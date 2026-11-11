"""`disc.json`: one disc's record in the library, in its folder of `raw/`.

It is the manifest as filed: the manifest's own models for the disc, its raw
copy and its titles, with paths where the files are now, relative to the
disc's folder, and the identity decided rather than the producer's claims.
*Target layout*, in the design, says why it isn't the manifest copied as it
stands. Absent means not recorded and null means none, as in the manifest.
`docs/disc.schema.json` is generated from these models (`python -m
reelbarrow.disc_record`).
"""

import json
import re
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import ConfigDict, Field, field_validator, model_validator

from reelbarrow.manifest import (
    Absent,
    Check,
    CheckState,
    Disc,
    DiscKey,
    Model,
    Part,
    RawForm,
    TitleReason,
)

SCHEMA = 1
FILENAME = "disc.json"
SCHEMA_FILE = Path(__file__).parents[2] / "docs" / "disc.schema.json"


class FiledRef(Model):
    """A file, by its path from the disc's own folder in `raw/`."""

    path: str = Field(
        description="`/` separators; `..` only to climb out of the disc's "
        "folder, before any name; no `.`; the name exactly as on disk."
    )

    @field_validator("path")
    @classmethod
    def _relative(cls, path: str) -> str:
        if not path or "\0" in path or path.startswith("/"):
            raise ValueError(f"{path!r} is not a path relative to the disc's folder")
        names = path.split("/")
        while names and names[0] == "..":
            names.pop(0)
        if not names or any(name in ("", ".", "..") for name in names):
            raise ValueError(f"{path!r}: `..` only before any name, and no `.`")
        return path


class FiledFrom(Model):
    """The manifest the disc was filed from."""

    source: str
    id: str
    manifest_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")] = Field(
        description="Of its content, as the plan's basis has it."
    )


class Film(Model):
    tmdb_id: int
    imdb_id: str | None = None


class FiledRaw(Model):
    """The raw copy, as the manifest's `raw` records it, without its folder:
    the record is in it."""

    never_null = frozenset({"image", "check", "problems", "titles_compared"})

    form: RawForm
    image: FiledRef | Absent = None
    check: Check | Absent = Field(default=None, description="Left out: never checked.")
    problems: list[str] | Absent = None
    titles_compared: Literal[True] | Absent = None

    @model_validator(mode="after")
    def _as_the_manifests(self) -> Self:
        if self.image is not None and self.form is not RawForm.DVD_IMAGE:
            raise ValueError(f"a {self.form} has no image")
        if (self.check is None) != (self.problems is None):
            raise ValueError("problems are recorded exactly when checks are")
        if self.check is not None:
            failed = CheckState.FAILED in (self.check.sizes, self.check.hashes)
            if failed != bool(self.problems):
                raise ValueError("problems are listed exactly when a check failed")
        return self


class FiledTitle(Model):
    """A title as filed: the manifest's title, its paths where its files are
    now. A title from before the raw copy's record has no disc number, only
    its MKV."""

    never_null = frozenset(
        {"disc_title", "playlist", "extracted", "played_by", "interleaved", "parts"}
    )

    disc_title: Annotated[int, Field(ge=1)] | Absent = None
    playlist: Annotated[str, Field(pattern=r"(?i)^\d{5}\.mpls$")] | Absent = None
    extracted: FiledRef | Absent = Field(
        default=None, description="The title's own MKV, kept in the raw copy."
    )
    transcode: FiledRef | None = Field(
        default=None,
        description="The library file it became. Null: none, and `reason` says why.",
    )
    reason: TitleReason | None = None
    played_by: DiscKey | Absent = None
    interleaved: bool | Absent = None
    parts: list[Part] | Absent = Field(default=None, min_length=2)

    @model_validator(mode="after")
    def _as_the_manifests(self) -> Self:
        if self.disc_title is not None and self.playlist is not None:
            raise ValueError("a title has a disc_title or a playlist, not both")
        if self.disc_title is None and self.playlist is None and self.extracted is None:
            raise ValueError("a title is known by its disc number or its MKV")
        if (self.transcode is None) != (self.reason is not None):
            raise ValueError("a reason exactly when there is no transcode")
        if (self.parts is None) != (self.interleaved is None):
            raise ValueError("a whole has both parts and interleaved")
        return self


class DiscRecord(Model):
    """`disc.json`. *Target layout*, in reelbarrow's design."""

    schema_: Literal[1] = Field(alias="schema")
    from_: FiledFrom = Field(alias="from")
    films: list[Film] = Field(
        min_length=1,
        description="What the disc holds, the first the film whose folder this is.",
    )
    disc: Disc
    raw: FiledRaw
    titles: list[FiledTitle] = Field(min_length=1)

    model_config = ConfigDict(
        extra="ignore",
        frozen=True,
        populate_by_name=True,
        title="reelbarrow disc.json",
    )

    def to_json(self) -> dict:
        return self.model_dump(mode="json", by_alias=True, exclude_unset=True)


def schema() -> dict:
    """`disc.json`'s JSON Schema, as `docs/disc.schema.json` holds it."""
    document = DiscRecord.model_json_schema(by_alias=True, mode="validation")
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://github.com/DArtagan/reelbarrow/blob/main/docs/disc.schema.json",
        **document,
    }


def write_schema() -> None:
    SCHEMA_FILE.write_text(json.dumps(schema(), indent=2) + "\n")


if __name__ == "__main__":
    write_schema()
    print(re.sub(r"^.*?docs/", "docs/", str(SCHEMA_FILE)))
