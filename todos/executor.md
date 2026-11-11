# executor: one plan carried out, dry run still on

## Opening prompt

> Build reelbarrow's executor, which keeps each filing's record in the
> library, and carry out `reelbarrow plan`'s
> plan for job 34, *Those Daring Young Men…*, which files as *Monte Carlo or
> Bust! (1969)* and whose fixture is `tests/fixtures/dvd-film-raw-unrecorded/`: for real
> against a synthetic tree in the tests, and in dry run
> against the share. Read `todos/executor.md`, then step 7 of *The service*,
> *Target layout* and *Sidecars and embedded metadata* in `docs/design.md`, and
> *Rules that protect the library* in `AGENTS.md`. Dry run stays on: turning
> it off is [first-filing](first-filing.md).

## Why

The second of the steps in [README](README.md): one manifest, its outputs
handled. Writing to the share is where the most is unknown (the CIFS mount's
permissions, Plex's refresh and watched state), so the
code that does it is built while there is one plan to carry out.

## Scope

- **The executor**: the single choke point for every write, rename and delete
  under the video root, which refuses all of them while `dry_run` is true. Add
  the test that no other module writes there (*Rules that protect the
  library*). The one exception is the manifest exporter
  ([`docs/exporter.md`](../docs/exporter.md)): a separate process that
  never mounts the library and writes only inside its own `--out`. The test
  allows that module's writes there and nowhere else.
- **Order**: folders, then renames on the same filesystem, then sidecars,
  then leftover deletion, then the filing's record. Then a Plex partial scan of the touched
  folder (`/library/sections/{id}/refresh?path=…`), because Plex's own change
  detection cannot be relied on over CIFS. In dry run, every one of these is
  recorded as refused.
- **Sidecars**: NFO and artwork per *Sidecars and embedded metadata*, from TMDB
  and fanart.tv.
- **`raw/<LABEL> [<identity>]/disc.json`** and the ignore markers in every
  `raw/`. Besides identity and which raw title became which file, `disc.json`
  carries whatever *Any order* in the design compares that can't be measured
  from the file, such as the raw copy's backup checks.
- **The filing's record**, `filing-<source>-<id>.json` beside `disc.json`:
  the manifest as it was, the plan, and what each operation did. This
  replaced a ledger in SQLite under `REELBARROW_DATA_DIR`, which was built
  first and dropped before anything was filed (below).
- **`reelbarrow file [path]`** plans as `reelbarrow plan [path]` does, taking
  the same path, and hands each automatic plan to the executor. Review and
  hold plans are printed and left alone.

## Decisions

Will, 2026-11-10, asked while the executor was built:

- **An operation that fails part way** (a rename meeting `EACCES` after the
  film's folder was made): *"Stop, record it as incomplete"*, rather than
  undoing what was done, which can fail too and is more code acting on the
  share. Recorded in step 7 of *The service*.
- **No fanart.tv key**: `reelbarrow file` refuses to run (exit 2), as `plan`
  does without TMDB's token, rather than filing with TMDB's artwork only.
  Without it a film would lack its logo, clear art, disc and landscape art,
  and nothing would add them later.

Will, 2026-11-11, reviewing PR #22:

- **No ledger database**: *"let's go with this reelbarrow-log-in-library-folder
  approach and jetison the database ledger."* The reasons and his words on a
  filing that stops part way are under *Decisions already made* in the
  design. Nothing had been written to a real ledger, so nothing migrates.
  With it went the ledger's backup, a precondition of
  [first-filing](first-filing.md): the record is in the share's snapshots.

## Built (2026-11-10 to 11, branch `executor`)

`reelbarrow.executor` (`Writer`, the choke point, `Executor`, and
`FilingRecord`), `reelbarrow.sidecars`, `reelbarrow.fanart`,
`reelbarrow.plex`, TMDB's credits and images in `reelbarrow.tmdb`, and
`reelbarrow file`. The write guard is `tests/test_write_guard.py`, static,
and `tests/share_guard.py`, an audit hook every test that builds a share
takes through the `guarded` fixture. The first two done-when conditions
pass in the tests; the third needs a release.

`disc.json` is the manifest as filed (Will, 2026-11-11), and its format is
`reelbarrow.disc_record` and `docs/disc.schema.json`. *Target layout* in the
design says why it isn't a verbatim copy of the manifest, which was the first
thing asked. It has room for a recorded raw copy's backup checks, its
`disc_title`s and its wholes; job 34 has none of them, since it predates the
record. The spec that plans a recorded raw copy fills them in. The filing's
record keeps each filed unit's manifest, as it was.

What the deployment needs, for the third condition:

- `REELBARROW_FANART_KEY` in reelbarrow's secret: in, with Plex's token, URL
  and paths (deployed 2026-11-11).
- A release with this branch in it, and the pod on it.

## Secrets

fanart.tv's key, added to reelbarrow's secret in the deployment repository.
Plex's token goes in beside it, and its URL and paths in the Deployment
(Will, 2026-11-11: *"let's add these plex keys to the deployment repo
too"*), though dry run neither scans nor reads them;
[first-filing](first-filing.md) checks Plex answers.

## Done when

- A test carries out job 34's plan on a synthetic tree built from its fixture,
  with dry run off, and the tree ends in the layout its row of the fixtures
  table gives: film, sidecars, `raw/` with `disc.json` and the filing's
  record, nothing left behind.
- The test that nothing but the executor writes under the video root passes,
  and fails when a module is made to write there.
- `reelbarrow file` in the deployed pod, on job 34, reports every operation
  refused by dry run, and the share is unchanged.
