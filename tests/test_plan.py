"""The planner, held against the fixtures table's rows, one case at a time.

Cases are loaded by `cases.load`; each is named for what it holds:

- `dvd-film-raw-unrecorded`: a DVD film from before the raw copy's record,
  its completed folder holding the feature alone, and its raw copy the one
  MKV written while the job ran
"""

import re
from datetime import UTC, datetime

import cases
import pytest

from reelbarrow.analyse import Analysis, File, Video
from reelbarrow.disc_record import DiscRecord
from reelbarrow.intake import RawFound
from reelbarrow.manifest import IdentityReason, Manifest, State
from reelbarrow.plan import (
    ARTWORK,
    DeleteFolder,
    Gate,
    MakeFolder,
    Plan,
    Rename,
    Sidecar,
    Write,
    pairing,
    plan,
    render,
)

FILM_ONLY = "dvd-film-raw-unrecorded"
COMPLETED = (
    "import/automatic-ripping-machine/completed/movies/"
    "Those-Daring-Young-Men-in-Their-Jaunty-Jalopies (1969)"
)
RAW = "import/automatic-ripping-machine/raw/Those-Daring-Young-Men-in-Their-Jaunty-Jalopies"
FOLDER = "movies/Monte Carlo or Bust! (1969) {tmdb-38792}"
DISC = f"{FOLDER}/raw/THOSE_DARING_YOUNG_MEN [dvd-ef68a3c769a42a4f]"


def test_every_case_in_the_docstring_has_a_fixture():
    named = re.findall(r"^- `([a-z0-9-]+)`:", __doc__, re.MULTILINE)
    for case in named:
        assert cases.load(case)


@pytest.fixture
def case() -> cases.Case:
    return cases.load(FILM_ONLY)


def planned(
    case: cases.Case,
    manifest: Manifest | None = None,
    analysis: Analysis | None = None,
    tmdb: dict | None = None,
    library: cases.Library | None = None,
) -> Plan:
    from reelbarrow.tmdb import Recorded

    return plan(
        manifest or case.manifest,
        analysis or case.analysis,
        Recorded(tmdb or case.tmdb_replies),
        library or cases.Library(),
    )


def failed(made: Plan) -> list[str]:
    return [check.rule for check in made.checks if not check.passed]


def test_the_film_files_automatically_with_its_raw_beside_it(case):
    """The fixtures table's row: automatic, the film under TMDB's name and id,
    its raw MKV in the disc's own folder of `raw/`, and the folders ARM left
    deleted once empty."""
    made = planned(case)

    assert made.gate is Gate.AUTOMATIC, render(made)
    renames = [
        (op.source, op.target) for op in made.operations if isinstance(op, Rename)
    ]
    assert renames == [
        (
            f"{COMPLETED}/Those-Daring-Young-Men-in-Their-Jaunty-Jalopies (1969).mkv",
            f"{FOLDER}/Monte Carlo or Bust! (1969).mkv",
        ),
        (f"{RAW}/B1_t00.mkv", f"{DISC}/B1_t00.mkv"),
    ]
    folders = [op.path for op in made.operations if isinstance(op, MakeFolder)]
    assert folders == [FOLDER, f"{FOLDER}/raw", DISC]
    deleted = [op.path for op in made.operations if isinstance(op, DeleteFolder)]
    assert deleted == [COMPLETED, RAW]


def test_its_sidecars_are_planned_and_disc_json_says_what_became_what(case):
    made = planned(case)

    writes = {op.path: op for op in made.operations if isinstance(op, Write)}
    assert writes[f"{FOLDER}/movie.nfo"].sidecar is Sidecar.MOVIE_NFO
    assert writes[f"{FOLDER}/movie.nfo"].content == {
        "tmdb_id": 38792,
        "imdb_id": "tt0064688",
    }
    for name in ARTWORK:
        assert writes[f"{FOLDER}/{name}"].sidecar is Sidecar.ARTWORK
    for marker in (".ignore", ".nomedia"):
        assert writes[f"{FOLDER}/raw/{marker}"].sidecar is Sidecar.IGNORE_MARKER
        assert writes[f"{FOLDER}/raw/{marker}"].content is None
    assert writes[f"{DISC}/disc.json"].content == {
        "schema": 1,
        "from": {
            "source": "arm",
            "id": "34-178993082181",
            "manifest_sha256": made.basis.manifest_sha256,
        },
        "films": [{"tmdb_id": 38792, "imdb_id": "tt0064688"}],
        "disc": {
            "type": "dvd",
            "label": "THOSE_DARING_YOUNG_MEN",
            "crc64": "ef68a3c769a42a4f",
        },
        # The copy was never checked, so the record has no checks.
        "raw": {"form": "mkv-titles"},
        # Paired by content, with no disc number: the job predates the record.
        "titles": [
            {
                "extracted": {"path": "B1_t00.mkv"},
                "transcode": {"path": "../../Monte Carlo or Bust! (1969).mkv"},
            }
        ],
    }
    DiscRecord.model_validate(writes[f"{DISC}/disc.json"].content)


def test_operations_run_folders_and_renames_then_sidecars_then_leftovers(case):
    kinds = [type(op) for op in planned(case).operations]
    first_write = kinds.index(Write)
    first_delete = kinds.index(DeleteFolder)
    assert all(k in (MakeFolder, Rename) for k in kinds[:first_write])
    assert all(k is Write for k in kinds[first_write:first_delete])
    assert all(k is DeleteFolder for k in kinds[first_delete:])


def test_the_basis_holds_every_path_read_and_every_path_written(case):
    made = planned(case)
    basis = {state.path: state for state in made.basis.paths}

    for file in case.analysis.completed.files + case.analysis.raw[0].files:
        assert basis[file.path].present
        assert (basis[file.path].size, basis[file.path].mtime) == (
            file.size,
            file.mtime,
        )
    assert basis[COMPLETED].present and basis[RAW].present
    for op in made.operations:
        target = op.target if isinstance(op, Rename) else op.path
        if not isinstance(op, DeleteFolder):
            assert basis[target].present is False
    assert re.fullmatch(r"[0-9a-f]{64}", made.basis.manifest_sha256)


def test_a_plan_reads_back_as_written(case):
    made = planned(case)
    assert Plan.model_validate(made.to_json()) == made


def test_the_rendered_plan_names_its_gate_and_every_path(case):
    text = render(planned(case))
    assert text.startswith("arm 34-178993082181: automatic")
    assert f"{DISC}/disc.json" in text


# Each rule below, broken on its own, sends the whole plan to review.


def with_movie(case: cases.Case, **fields) -> dict:
    replies = {k: dict(v) for k, v in case.tmdb_replies.items()}
    replies["movie/38792"].update(fields)
    return replies


def with_files(analysis: Analysis, where: str, files: list[File]) -> Analysis:
    if where == "completed":
        completed = analysis.completed.model_copy(update={"files": files})
        return analysis.model_copy(update={"completed": completed})
    raw = analysis.raw[0].model_copy(update={"files": files})
    return analysis.model_copy(update={"raw": [raw]})


def test_a_feature_beyond_three_percent_of_tmdbs_runtime_is_reviewed(case):
    # The Hallelujah Trail: 155.5 min on the disc, 165 min on TMDB, -5.7%.
    made = planned(case, tmdb=with_movie(case, runtime=132))
    assert made.gate is Gate.REVIEW
    assert failed(made) == ["runtime"]


@pytest.mark.parametrize(
    ("off", "gate"), [(0.0299, Gate.AUTOMATIC), (0.0301, Gate.REVIEW)]
)
def test_three_percent_is_the_edge(case, off, gate):
    feature = case.analysis.completed.files[0]
    longer = feature.model_copy(
        update={
            "video": feature.video.model_copy(update={"duration": 122 * 60 * (1 + off)})
        }
    )
    source = case.analysis.raw[0].files[0]
    # Its stub chapter, no longer near the end, goes with the length.
    longer_source = source.model_copy(
        update={
            "video": Video(
                duration=longer.video.duration, chapters=source.video.chapters[:-1]
            )
        }
    )
    analysis = with_files(
        with_files(case.analysis, "completed", [longer]), "raw", [longer_source]
    )
    assert planned(case, analysis=analysis).gate is gate


@pytest.mark.parametrize(
    "reason",
    [IdentityReason.COPIED_FROM_EARLIER_JOB, IdentityReason.NOT_IDENTIFIED],
)
def test_an_identity_arm_did_not_look_up_is_reviewed(case, reason):
    identity = case.manifest.identity
    imdb = identity.imdb_id.model_copy(update={"reason": reason})
    manifest = case.manifest.model_copy(
        update={"identity": identity.model_copy(update={"imdb_id": imdb})}
    )
    made = planned(case, manifest=manifest)
    assert made.gate is Gate.REVIEW
    assert failed(made) == ["identified"]


def test_an_imdb_id_tmdb_has_twice_is_reviewed(case):
    replies = dict(case.tmdb_replies)
    replies["find/tt0064688"] = {"movie_results": [{"id": 38792}, {"id": 1}]}
    made = planned(case, tmdb=replies)
    assert failed(made) == ["tmdb"]


def test_a_failed_job_is_reviewed(case):
    manifest = case.manifest.model_copy(update={"state": State.FAILED})
    assert "state" in failed(planned(case, manifest=manifest))


def test_another_title_beside_the_feature_is_reviewed_and_nothing_deleted(case):
    feature = case.analysis.completed.files[0]
    extra = feature.model_copy(
        update={
            "path": f"{COMPLETED}/extras/title_2.mkv",
            "video": Video(duration=600.0, chapters=[]),
        }
    )
    made = planned(
        case, analysis=with_files(case.analysis, "completed", [feature, extra])
    )
    assert failed(made) == ["extras"]
    deleted = [op.path for op in made.operations if isinstance(op, DeleteFolder)]
    assert COMPLETED not in deleted


def test_a_raw_mkv_whose_chapters_differ_is_reviewed(case):
    source = case.analysis.raw[0].files[0]
    chapters = list(source.video.chapters)
    chapters[5] += 0.3
    moved = source.model_copy(
        update={"video": source.video.model_copy(update={"chapters": chapters})}
    )
    made = planned(case, analysis=with_files(case.analysis, "raw", [moved]))
    assert failed(made) == ["pairing"]
    assert not any(
        isinstance(op, Rename) and op.source == source.path for op in made.operations
    )


def test_a_second_file_in_the_raw_folder_is_reviewed(case):
    source = case.analysis.raw[0].files[0]
    other = source.model_copy(update={"path": f"{RAW}/C1_t01.mkv"})
    made = planned(case, analysis=with_files(case.analysis, "raw", [source, other]))
    assert made.gate is Gate.REVIEW


def test_no_raw_copy_found_is_reviewed(case):
    made = planned(case, analysis=case.analysis.model_copy(update={"raw": []}))
    assert failed(made) == ["raw copy"]


def test_mkvs_written_into_two_folders_while_the_job_ran_are_reviewed(case):
    second = case.analysis.raw[0].model_copy(update={"path": f"{RAW}_2"})
    analysis = case.analysis.model_copy(update={"raw": [case.analysis.raw[0], second]})
    assert failed(planned(case, analysis=analysis)) == ["raw copy"]


def test_a_recorded_raw_copy_is_not_planned_yet(case):
    raw = {
        "form": "dvd-image",
        "folder": {"path": RAW},
        "image": {"path": f"{RAW}/disc.iso"},
        "check": {"sizes": "passed", "hashes": "passed"},
        "problems": [],
    }
    manifest = Manifest.model_validate({**case.manifest.to_json(), "raw": raw})
    found = case.analysis.raw[0].model_copy(update={"found": RawFound.RECORDED})
    analysis = case.analysis.model_copy(update={"raw": [found]})
    assert failed(planned(case, manifest=manifest, analysis=analysis)) == ["raw copy"]


def test_a_path_the_manifest_records_and_the_share_lacks_is_reviewed(case):
    analysis = case.analysis.model_copy(
        update={"completed": None, "missing": [COMPLETED]}
    )
    made = planned(case, analysis=analysis)
    assert {"recorded paths", "completed folder"} <= set(failed(made))


@pytest.mark.parametrize(
    "existing",
    [
        "Monte Carlo or Bust! (1969) {tmdb-38792}",
        "Monte Carlo or Bust! (1969)",
        "Those Daring Young Men (1969) {tmdb-38792}",
    ],
)
def test_a_film_already_in_the_library_is_reviewed(case, existing):
    made = planned(case, library=cases.Library(folders=[existing]))
    assert failed(made) == ["library"]


def test_a_target_already_there_is_reviewed(case):
    when = datetime(2026, 1, 1, tzinfo=UTC)
    made = planned(
        case, library=cases.Library.holding(f"{FOLDER}/poster.jpg", when=when)
    )
    assert failed(made) == ["library"]
    assert {s.path: s.present for s in made.basis.paths}[f"{FOLDER}/poster.jpg"]


def test_a_name_with_nothing_writable_is_reviewed(case):
    assert "name" in failed(planned(case, tmdb=with_movie(case, title="???")))


def test_names_are_folded_for_the_share(case):
    made = planned(case, tmdb=with_movie(case, title="Monte Carlo: or Bust\u2026"))
    assert made.gate is Gate.AUTOMATIC
    assert (
        made.operations[0].path == "movies/Monte Carlo - or Bust... (1969) {tmdb-38792}"
    )


def test_an_analysis_of_another_job_is_refused(case):
    other = case.analysis.model_copy(update={"id": "35-178994616115"})
    with pytest.raises(ValueError, match="35-178994616115"):
        planned(case, analysis=other)


# The pairing rule, at its edges.


def video(duration: float, *chapters: float) -> Video:
    return Video(duration=duration, chapters=list(chapters))


def test_pairing_allows_a_quarter_second():
    assert pairing(video(100.0, 0, 50.0), video(100.25, 0, 50.25))[0]
    assert not pairing(video(100.0, 0, 50.0), video(100.26, 0, 50.0))[0]
    assert not pairing(video(100.0, 0, 50.0), video(100.0, 0, 50.26))[0]


def test_pairing_allows_the_stub_chapter_handbrake_drops():
    # Job 34's: 1.03 s before the end, and the transcode has one fewer.
    assert pairing(video(100.0, 0, 50.0, 98.97), video(100.0, 0, 50.0))[0]
    assert not pairing(video(100.0, 0, 50.0, 98.4), video(100.0, 0, 50.0))[0]
    assert not pairing(video(100.0, 0, 50.0), video(100.0, 0, 50.0, 98.97))[0]


def test_an_mkv_without_chapters_has_one_at_zero():
    assert pairing(video(100.0), video(100.0, 0))[0]
