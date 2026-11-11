"""`disc.json`: the manifest as filed, in the manifest's own vocabulary."""

import json

import pytest
from pydantic import ValidationError

from reelbarrow import disc_record
from reelbarrow.disc_record import DiscRecord, FiledRef, FiledTitle
from reelbarrow.manifest import Title

SHA = "0" * 64
RECORD = {
    "schema": 1,
    "from": {"source": "arm", "id": "87-179323748073", "manifest_sha256": SHA},
    "films": [{"tmdb_id": 20662, "imdb_id": "tt0955308"}],
    "disc": {"type": "dvd", "label": "ROBIN_HOOD", "crc64": "d3c5ce89aef40f61"},
    "raw": {
        "form": "dvd-image",
        "image": {"path": "Robin Hood.iso"},
        "check": {"sizes": "passed", "hashes": "passed"},
        "problems": [],
        "titles_compared": True,
    },
    "titles": [
        {
            "disc_title": 1,
            "transcode": {"path": "../../Robin Hood (2010).mkv"},
            "reason": None,
            "interleaved": False,
            "parts": [
                {"disc_title": 2, "start": 0.0},
                {"disc_title": 3, "start": 1086.118},
            ],
        },
        {"disc_title": 2, "transcode": None, "reason": "played_by_kept_titles"},
    ],
}


def test_the_schema_file_is_current():
    committed = json.loads(disc_record.SCHEMA_FILE.read_text())
    assert committed == disc_record.schema(), "run: python -m reelbarrow.disc_record"


def test_a_recorded_disc_reads_back_as_written():
    record = DiscRecord.model_validate(RECORD)
    assert record.to_json() == RECORD


def test_a_filed_title_is_the_manifests_title_with_its_paths_moved():
    # Everything but the paths carries over from a manifest's title as it is.
    manifest_title = Title.model_validate(
        {
            "disc_title": 2,
            "extracted": {"path": "import/arm/raw/Robin Hood/titles/E2_t01.mkv"},
            "transcode": None,
            "reason": "played_by_kept_titles",
        }
    )
    carried = manifest_title.model_dump(exclude_unset=True, exclude={"extracted"})
    filed = FiledTitle.model_validate(carried)
    assert filed.model_dump(exclude_unset=True) == carried


def test_a_copy_never_checked_records_no_checks():
    record = DiscRecord.model_validate({**RECORD, "raw": {"form": "mkv-titles"}})
    assert "check" not in record.to_json()["raw"]


@pytest.mark.parametrize(
    "path",
    ["B1_t00.mkv", "../../Robin Hood (2010).mkv", "../../../Other (1990)/a.mkv"],
)
def test_a_path_is_from_the_discs_folder(path):
    assert FiledRef(path=path).path == path


@pytest.mark.parametrize(
    "path", ["", "/video/movies/a.mkv", "a/../b.mkv", "./a.mkv", "a//b.mkv", "..", "a/"]
)
def test_a_path_that_isnt_plainly_relative_is_refused(path):
    with pytest.raises(ValidationError):
        FiledRef(path=path)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda r: r["raw"].update(form="mkv-titles"), "has no image"),
        (lambda r: r["raw"].pop("problems"), "exactly when checks are"),
        (
            lambda r: r["raw"].update(check={"sizes": "failed", "hashes": "passed"}),
            "exactly when a check failed",
        ),
        (lambda r: r["titles"][1].update(reason=None), "a reason exactly"),
        (lambda r: r["titles"][0].update(playlist="00001.mpls"), "not both"),
        (lambda r: r["titles"][1].pop("disc_title"), "disc number or its MKV"),
        (lambda r: r["titles"][0].pop("interleaved"), "both parts and interleaved"),
        (lambda r: r.update(films=[]), "at least 1"),
        (lambda r: r.update(titles=[]), "at least 1"),
    ],
)
def test_each_rule_refuses_a_record_that_breaks_it(change, message):
    record = json.loads(json.dumps(RECORD))
    change(record)
    with pytest.raises(ValidationError, match=message):
        DiscRecord.model_validate(record)
