"""The executor, carrying out job 34's plan on a synthetic share built from its
fixture (`cases.Case.build`), live and in dry run.

The fixtures table's row: *Monte Carlo or Bust! (1969) {tmdb-38792}*, film
only, its sidecars, `raw/` holding the disc's folder with `disc.json` and the
filing's record, and nothing left behind of the job in `completed/` or `raw/`.

The case's files are sparse placeholders, with nothing for mkvpropedit to
edit, so the writer's tag is a stand-in here (`tagged`); `test_tag` and
`test_cli` tag real MKVs.
"""

import json
import os
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

import cases
import httpx
import pytest

from reelbarrow import fanart
from reelbarrow.disc_record import DiscRecord
from reelbarrow.executor import (
    FILING_SCHEMA_FILE,
    Executor,
    FilingRecord,
    Outcome,
    Refused,
    Result,
    Writer,
    WriterError,
    filing_schema,
    render_report,
)
from reelbarrow.plan import ARTWORK, Gate, Plan, ShareLibrary, plan
from reelbarrow.plex import Plex
from reelbarrow.sidecars import MAGIC, Sources
from reelbarrow.tmdb import Recorded

ARM = "import/automatic-ripping-machine"
COMPLETED = (
    f"{ARM}/completed/movies/Those-Daring-Young-Men-in-Their-Jaunty-Jalopies (1969)"
)
RAW = f"{ARM}/raw/Those-Daring-Young-Men-in-Their-Jaunty-Jalopies"
FOLDER = "movies/Monte Carlo or Bust! (1969) {tmdb-38792}"
DISC = f"{FOLDER}/raw/THOSE_DARING_YOUNG_MEN [dvd-ef68a3c769a42a4f]"
FILM = f"{FOLDER}/Monte Carlo or Bust! (1969).mkv"
RECORD = f"{DISC}/filing-arm-34-178993082181.json"
NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)


class Images:
    """Artwork by its URL: the format its name says, and nothing else."""

    def __init__(self) -> None:
        self.fetched: list[str] = []

    def fetch(self, url: str) -> bytes:
        self.fetched.append(url)
        return MAGIC[PurePosixPath(url).suffix] + url.encode()


class PlexServer:
    """Plex's two requests: its sections, and a partial scan.

    Its locations are paths inside Plex's own container, not on the share:
    the deployment's Plex mounts the share's `movies` at `/data/movies`. The
    executor is told that mapping (`REELBARROW_PLEX_PATHS`), and these are
    this test's copy of it.
    """

    def __init__(self) -> None:
        self.scanned: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/library/sections":
            directories = [
                {"key": "1", "Location": [{"path": "/data/movies"}]},
                {"key": "2", "Location": [{"path": "/data/shows"}]},
            ]
            return httpx.Response(
                200, json={"MediaContainer": {"Directory": directories}}
            )
        if request.url.path == "/library/sections/1/refresh":
            self.scanned.append(request)
            return httpx.Response(200)
        return httpx.Response(404)


FEATURE = f"{COMPLETED}/Those-Daring-Young-Men-in-Their-Jaunty-Jalopies (1969).mkv"
TAGS = {
    "TITLE": "Monte Carlo or Bust!",
    "DATE_RELEASED": "1969-04-28",
    "IMDB": "tt0064688",
    "TMDB": "movie/38792",
}


@pytest.fixture(autouse=True)
def tagged(monkeypatch) -> list[tuple[str, str, dict]]:
    """The writer's tag, refused in dry run as the writer's own is, and
    otherwise only recorded."""
    calls = []

    def tag(self, path, title, tags):
        self._refuse_in_dry_run()
        calls.append((path, title, dict(tags)))
        return "read back"

    monkeypatch.setattr(Writer, "tag", tag)
    return calls


@pytest.fixture
def case() -> cases.Case:
    return cases.load("dvd-film-raw-unrecorded")


@pytest.fixture
def root(tmp_path, case, guarded) -> Path:
    root = tmp_path / "video"
    case.build(root)
    (root / "movies").mkdir()
    guarded(root)
    return root


def tree(root: Path) -> dict[str, int | None]:
    """Every entry under the root: a file's size, a folder's None."""
    return {
        p.relative_to(root).as_posix(): None if p.is_dir() else p.stat().st_size
        for p in sorted(root.rglob("*"))
    }


@pytest.fixture
def plex_server() -> PlexServer:
    return PlexServer()


class Run:
    """The executor and one unit's sources, as the CLI makes them: the TMDB
    client the unit is planned with is the one its filing uses, so its record
    holds every reply either read."""

    def __init__(self, executor: Executor, sources: Sources, root: Path, case):
        self.executor = executor
        self.sources = sources
        self.root = root
        self.case = case

    def plan(self) -> Plan:
        library = ShareLibrary(self.root, "movies")
        case = self.case
        return plan(case.manifest, case.analysis, self.sources.tmdb, library, "movies")

    def carry_out(self, made: Plan, manifest):
        return self.executor.carry_out(made, manifest, self.case.analysis, self.sources)


def executor(
    root: Path,
    case: cases.Case,
    *,
    dry_run: bool,
    plex_server: PlexServer | None = None,
    fanart_replies: dict | None = None,
) -> Run:
    plex = Plex(
        "http://plex:32400",
        "plex-token",
        {"movies": "/data/movies"},
        transport=httpx.MockTransport(plex_server or PlexServer()),
    )
    sources = Sources(
        tmdb=Recorded(case.tmdb_replies),
        fanart=fanart.Recorded(
            case.fanart_replies if fanart_replies is None else fanart_replies
        ),
        images=Images(),
    )
    run = Executor(
        writer=Writer(root, dry_run=dry_run),
        libraries=["movies"],
        plex=plex,
        clock=lambda: NOW,
    )
    return Run(run, sources, root, case)


def planned(root: Path, case: cases.Case) -> Plan:
    made = plan(
        case.manifest, case.analysis, case.tmdb, ShareLibrary(root, "movies"), "movies"
    )
    assert made.gate is Gate.AUTOMATIC
    assert made.record == RECORD
    return made


def test_job_34_files_into_its_rows_layout(root, case, plex_server, tagged):
    """The executor spec's first done-when, with dry run off."""
    film_inode = (root / COMPLETED / f"{COMPLETED.split('/')[-1]}.mkv").stat().st_ino
    made = planned(root, case)

    report = executor(root, case, dry_run=False, plex_server=plex_server).carry_out(
        made, case.manifest
    )

    assert report.result is Result.FILED, render_report(report)
    # Tagged where ARM left it, before anything moved.
    assert tagged == [(FEATURE, "Monte Carlo or Bust!", TAGS)]
    assert report.steps[1].step == "tag"
    assert report.steps[1].outcome is Outcome.DONE
    artwork = {
        PurePosixPath(step.subject).name
        for step in report.steps
        if step.step == "write" and step.outcome is Outcome.DONE
    } & set(ARTWORK)
    # TMDB has a poster and a textless backdrop, and no logo. fanart.tv has
    # only a German clear art, and art in another language is never used.
    assert artwork == {"poster.jpg", "fanart.jpg"}
    skipped = {
        PurePosixPath(step.subject).name
        for step in report.steps
        if step.outcome is Outcome.SKIPPED
    }
    assert skipped == {"clearlogo.png", "clearart.png", "landscape.jpg", "disc.png"}
    expected_files = {
        FILM: 1821842964,
        f"{FOLDER}/movie.nfo": None,
        **{f"{FOLDER}/{name}": None for name in artwork},
        f"{FOLDER}/raw/.ignore": 0,
        f"{FOLDER}/raw/.nomedia": 0,
        f"{DISC}/B1_t00.mkv": 4331224636,
        f"{DISC}/disc.json": None,
        RECORD: None,
    }
    expected_folders = {
        "import",
        ARM,
        f"{ARM}/completed",
        f"{ARM}/completed/movies",
        f"{ARM}/raw",
        "movies",
        FOLDER,
        f"{FOLDER}/raw",
        DISC,
    }
    found = tree(root)
    assert set(found) == set(expected_files) | expected_folders
    for path, size in expected_files.items():
        if size is not None:
            assert found[path] == size, path
    # Renamed, not copied.
    assert (root / FILM).stat().st_ino == film_inode
    # disc.json's paths are where the files are now, from the disc's folder.
    disc = DiscRecord.model_validate_json((root / DISC / "disc.json").read_bytes())
    (title,) = disc.titles
    assert (root / DISC / title.extracted.path).resolve() == root / DISC / "B1_t00.mkv"
    assert (root / DISC / title.transcode.path).resolve() == (root / FILM).resolve()
    assert disc.films[0].tmdb_id == 38792
    nfo = ET.parse(root / FOLDER / "movie.nfo").getroot()
    assert nfo.findtext("title") == "Monte Carlo or Bust!"
    assert nfo.find("uniqueid[@type='tmdb']").text == "38792"
    assert nfo.find("uniqueid[@type='imdb']").text == "tt0064688"
    # Plex scans the film's folder, by its own path to it.
    (scan,) = plex_server.scanned
    assert scan.url.params["path"] == f"/data/{FOLDER}"
    assert scan.headers["x-plex-token"] == "plex-token"
    assert "plex-token" not in str(scan.url)


def test_the_record_says_what_was_filed_from_what(root, case):
    run = executor(root, case, dry_run=False)
    made = run.plan()
    report = run.carry_out(made, case.manifest)

    record = FilingRecord.model_validate_json((root / RECORD).read_bytes())
    assert record.result is Result.FILED
    assert (record.started, record.finished) == (NOW, NOW)
    # The manifest as it was, which disc.json doesn't keep, and the plan with
    # the evidence its checks passed on.
    assert record.manifest.to_json() == case.manifest.to_json()
    assert record.plan == made
    assert len(record.steps) == len(made.operations)
    assert {s.outcome for s in record.steps} <= {Outcome.DONE, Outcome.SKIPPED}
    recorded = next(s for s in report.steps if s.step == "record")
    assert recorded.outcome is Outcome.DONE


def test_the_record_holds_the_case_a_regression_fixture_is(root, case, tmp_path):
    """Everything the plan was made from, as it was: written out as a case's
    files, it loads and plans again to the plan that was carried out."""
    run = executor(root, case, dry_run=False)
    made = run.plan()
    run.carry_out(made, case.manifest)
    record = FilingRecord.model_validate_json((root / RECORD).read_bytes())

    # Exactly the case's own files: TMDB's four replies, planning's and
    # filing's both, and fanart.tv's one.
    assert record.analysis == case.analysis
    assert record.replies.tmdb == case.tmdb_replies
    assert record.replies.fanart == case.fanart_replies

    rebuilt = tmp_path / "fixtures" / "from-the-record"
    rebuilt.mkdir(parents=True)
    for name, document in [
        ("manifest.json", record.manifest.to_json()),
        ("analysis.json", record.analysis.to_json()),
        ("tmdb.json", record.replies.tmdb),
        ("fanart.json", record.replies.fanart),
    ]:
        (rebuilt / name).write_text(json.dumps(document))
    replayed = cases.load(rebuilt.name, fixtures=rebuilt.parent)
    again = plan(
        replayed.manifest,
        replayed.analysis,
        replayed.tmdb,
        cases.Library(),
        "movies",
    )
    assert again == record.plan


def test_the_record_keeps_the_manifest_in_its_own_form(root, case):
    run = executor(root, case, dry_run=False)
    run.carry_out(run.plan(), case.manifest)
    written = json.loads((root / RECORD).read_bytes())
    # Exactly as the manifest's own JSON: fields never recorded stay absent.
    assert written["manifest"] == case.manifest.to_json()
    assert "raw" not in written["manifest"]


def test_the_filing_schema_file_is_current():
    committed = json.loads(FILING_SCHEMA_FILE.read_text())
    assert committed == filing_schema(), "run: python -m reelbarrow.executor"


def test_a_unit_filed_is_not_filed_again(root, case):
    made = planned(root, case)
    run = executor(root, case, dry_run=False)
    run.carry_out(made, case.manifest)

    again = run.carry_out(made, case.manifest)
    assert again.result is Result.BASIS_CHANGED
    assert f"{RECORD} appeared" in again.steps[0].detail


def test_dry_run_refuses_every_change_and_the_share_is_unchanged(
    root, case, plex_server
):
    before = {
        p.relative_to(root).as_posix(): (p.stat().st_mtime_ns, p.stat().st_size)
        for p in root.rglob("*")
    }
    made = planned(root, case)

    report = executor(root, case, dry_run=True, plex_server=plex_server).carry_out(
        made, case.manifest
    )

    assert report.result is Result.DRY_RUN, render_report(report)
    after = {
        p.relative_to(root).as_posix(): (p.stat().st_mtime_ns, p.stat().st_size)
        for p in root.rglob("*")
    }
    assert after == before
    steps = {step.step: [] for step in report.steps}
    for step in report.steps:
        steps[step.step].append(step.outcome)
    assert steps.pop("basis") == [Outcome.DONE]
    # Every operation refused, but an artwork neither provider has.
    for name, seen in steps.items():
        allowed = (
            {Outcome.REFUSED, Outcome.SKIPPED} if name == "write" else {Outcome.REFUSED}
        )
        assert set(seen) <= allowed, name
    assert steps["tag"] == [Outcome.REFUSED]
    assert len(steps["record"]) == 1 and len(steps["plex_scan"]) == 1
    assert plex_server.scanned == []


def test_a_basis_that_changed_does_nothing(root, case):
    made = planned(root, case)
    raw = root / RAW / "B1_t00.mkv"
    os.utime(raw, ns=(0, 0))

    report = executor(root, case, dry_run=False).carry_out(made, case.manifest)
    assert report.result is Result.BASIS_CHANGED
    assert f"{RAW}/B1_t00.mkv changed" in report.steps[0].detail
    assert not (root / FOLDER).exists()


def test_a_target_that_appeared_since_planning_does_nothing(root, case):
    made = planned(root, case)
    (root / FOLDER).mkdir()

    report = executor(root, case, dry_run=False).carry_out(made, case.manifest)
    assert report.result is Result.BASIS_CHANGED
    assert f"{FOLDER} appeared" in report.steps[0].detail


def test_a_changed_manifest_does_nothing(root, case):
    made = planned(root, case)
    changed = case.manifest.model_copy(update={"errors": "later"})
    report = executor(root, case, dry_run=False).carry_out(made, changed)
    assert report.result is Result.BASIS_CHANGED
    assert "the manifest" in report.steps[0].detail


def test_a_provider_that_cant_be_reached_stops_the_filing_before_anything_moves(
    root, case
):
    made = planned(root, case)
    before = tree(root)
    report = executor(
        root, case, dry_run=False, fanart_replies={"movies/1": {}}
    ).carry_out(made, case.manifest)

    assert report.result is Result.NOT_RENDERED
    assert "no recorded reply" in report.steps[-1].detail
    assert tree(root) == before


def test_every_folder_is_made_before_anything_moves(root, case):
    kinds = [op.op for op in planned(root, case).operations]
    assert kinds.index("rename") > max(
        i for i, kind in enumerate(kinds) if kind == "make_folder"
    )


def test_an_operation_that_fails_stops_the_rest_and_the_record_says_so(
    root, case, monkeypatch, plex_server
):
    made = planned(root, case)
    renames = []
    original = Writer.rename

    def rename(self, source, target):
        renames.append(source)
        if len(renames) == 2:
            raise PermissionError(13, "Permission denied", target)
        original(self, source, target)

    monkeypatch.setattr(Writer, "rename", rename)
    report = executor(root, case, dry_run=False, plex_server=plex_server).carry_out(
        made, case.manifest
    )

    assert report.result is Result.INCOMPLETE
    operations = [step for step in report.steps if step.step not in ("basis", "record")]
    seen = [step.outcome for step in operations]
    failed = seen.index(Outcome.FAILED)
    assert set(seen[:failed]) == {Outcome.DONE}
    assert set(seen[failed + 1 :]) == {Outcome.NOT_RUN}
    assert "Permission denied" in operations[failed].detail
    # The film moved; its raw copy and everything after didn't.
    assert (root / FILM).exists() and (root / RAW / "B1_t00.mkv").exists()
    assert not (root / FOLDER / "movie.nfo").exists()
    assert plex_server.scanned == []
    # The record, in the disc's folder made before anything moved, says the
    # same.
    assert report.steps[-1].step == "record"
    assert report.steps[-1].outcome is Outcome.DONE
    record = FilingRecord.model_validate_json((root / RECORD).read_bytes())
    assert record.result is Result.INCOMPLETE
    assert record.steps == operations


def test_a_filing_that_stops_before_its_folders_are_made_says_so(
    root, case, monkeypatch
):
    made = planned(root, case)

    def make_folder(self, path):
        raise PermissionError(13, "Permission denied", path)

    monkeypatch.setattr(Writer, "make_folder", make_folder)
    report = executor(root, case, dry_run=False).carry_out(made, case.manifest)

    assert report.result is Result.INCOMPLETE
    # The film was tagged, nothing was filed, and the report says both.
    outcomes = [step.outcome for step in report.steps[1:-1]]
    assert outcomes[:2] == [Outcome.DONE, Outcome.FAILED]
    assert set(outcomes[2:]) == {Outcome.NOT_RUN}
    assert report.steps[-1].step == "record"
    assert report.steps[-1].outcome is Outcome.NOT_RUN
    assert "nothing was filed" in report.steps[-1].detail
    assert not (root / FOLDER).exists()


def test_a_tag_that_fails_stops_the_filing_with_nothing_moved(
    root, case, monkeypatch, plex_server
):
    made = planned(root, case)
    before = tree(root)

    def tag(self, path, title, tags):
        raise WriterError(f"{path} was edited, but mkvinfo finds fault with it")

    monkeypatch.setattr(Writer, "tag", tag)
    report = executor(root, case, dry_run=False, plex_server=plex_server).carry_out(
        made, case.manifest
    )

    assert report.result is Result.INCOMPLETE
    basis, first, *rest, record = report.steps
    assert basis.outcome is Outcome.DONE
    assert (first.step, first.outcome) == ("tag", Outcome.FAILED)
    assert "mkvinfo finds fault" in first.detail
    assert {step.outcome for step in rest} == {Outcome.NOT_RUN}
    # The library is untouched, so there is no record there: the report is
    # the account.
    assert (record.step, record.outcome) == ("record", Outcome.NOT_RUN)
    assert tree(root) == before
    assert plex_server.scanned == []


def test_only_an_automatic_plan_is_carried_out(root, case):
    made = planned(root, case).model_copy(update={"gate": Gate.REVIEW})
    with pytest.raises(ValueError, match="review"):
        executor(root, case, dry_run=False).carry_out(made, case.manifest)


def test_a_plan_with_no_place_for_its_record_is_not_carried_out(root, case):
    made = planned(root, case).model_copy(update={"record": None})
    with pytest.raises(ValueError, match="record"):
        executor(root, case, dry_run=False).carry_out(made, case.manifest)


def test_the_report_reads_for_a_person(root, case):
    report = executor(root, case, dry_run=True).carry_out(
        planned(root, case), case.manifest
    )
    text = render_report(report)
    assert text.startswith("arm 34-178993082181: dry_run")
    assert f"refused  rename        {COMPLETED}" in text


# The writer, the share's one choke point, on its own.


@pytest.fixture
def root_a(tmp_path, guarded) -> Path:
    root = tmp_path / "video"
    (root / "a").mkdir(parents=True)
    (root / "a" / "file.mkv").write_bytes(b"film")
    guarded(root)
    return root


@pytest.mark.parametrize(
    ("method", "args"),
    [
        ("make_folder", ("b",)),
        ("rename", ("a/file.mkv", "a/moved.mkv")),
        ("write", ("a/new.nfo", b"x")),
        ("delete_folder", ("a",)),
        # Refused before the path is even looked at.
        ("write", ("../outside", b"x")),
    ],
)
def test_dry_run_refuses_each_change_before_touching_the_share(root_a, method, args):
    before = tree(root_a)
    with pytest.raises(Refused):
        getattr(Writer(root_a), method)(*args)
    assert tree(root_a) == before


def test_dry_run_is_the_default():
    assert Writer(Path("/video")).dry_run is True


def test_a_rename_never_lands_on_something(root_a):
    (root_a / "a" / "other.mkv").write_bytes(b"other")
    with pytest.raises(WriterError, match="already there"):
        Writer(root_a, dry_run=False).rename("a/file.mkv", "a/other.mkv")
    assert (root_a / "a" / "other.mkv").read_bytes() == b"other"


def test_a_write_never_replaces_a_file(root_a):
    with pytest.raises(WriterError, match="already there"):
        Writer(root_a, dry_run=False).write("a/file.mkv", b"nfo")
    assert (root_a / "a" / "file.mkv").read_bytes() == b"film"


def test_a_folder_holding_anything_is_not_deleted(root_a):
    with pytest.raises(OSError):
        Writer(root_a, dry_run=False).delete_folder("a")
    assert (root_a / "a" / "file.mkv").exists()


def test_a_path_out_of_the_share_is_refused(root_a, tmp_path):
    with pytest.raises(ValueError):
        Writer(root_a, dry_run=False).write("../outside", b"x")
    assert not (tmp_path / "outside").exists()


def test_a_path_through_a_link_is_refused(root_a, tmp_path):
    (tmp_path / "elsewhere").mkdir()
    (root_a / "link").symlink_to(tmp_path / "elsewhere")
    with pytest.raises(WriterError, match="link"):
        Writer(root_a, dry_run=False).write("link/new.nfo", b"x")
    assert list((tmp_path / "elsewhere").iterdir()) == []


def test_a_link_is_never_renamed(root_a):
    (root_a / "a" / "link.mkv").symlink_to(root_a / "a" / "file.mkv")
    with pytest.raises(WriterError, match="neither"):
        Writer(root_a, dry_run=False).rename("a/link.mkv", "a/moved.mkv")
