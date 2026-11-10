# executor: one plan carried out, dry run still on

## Opening prompt

> Build reelbarrow's executor and ledger, and carry out `reelbarrow plan`'s
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
permissions, Plex's refresh and watched state, the ledger's backup), so the
code that does it is built while there is one plan to carry out.

## Scope

- **The executor**: the single choke point for every write, rename and delete
  under the video root, which refuses all of them while `dry_run` is true. Add
  the test that no other module writes there (*Rules that protect the
  library*). The one exception is the manifest exporter
  ([`docs/exporter.md`](../docs/exporter.md)): a separate process that
  never mounts the library and writes only inside its own `--out`. The test
  allows that module's writes there and nowhere else.
- **Order**: renames on the same filesystem, then sidecars, then leftover
  deletion, then the ledger entry. Then a Plex partial scan of the touched
  folder (`/library/sections/{id}/refresh?path=…`), because Plex's own change
  detection cannot be relied on over CIFS. In dry run, every one of these is
  recorded as refused.
- **Sidecars**: NFO and artwork per *Sidecars and embedded metadata*, from TMDB
  and fanart.tv.
- **`raw/<LABEL> [<identity>]/disc.json`** and the ignore markers in every
  `raw/`. Besides identity and which raw title became which file, `disc.json`
  carries whatever *Any order* in the design compares that can't be measured
  from the file, such as the raw copy's backup checks.
- **The ledger**, in SQLite under `REELBARROW_DATA_DIR`, keyed by the
  manifest's `source` and `id` (*The manifest*).
- **`reelbarrow file [path]`** plans as `reelbarrow plan [path]` does, taking
  the same path, and hands each automatic plan to the executor. Review and
  hold plans are printed and left alone.

## Secrets

fanart.tv's key, added to reelbarrow's secret in the deployment repository.
Plex's token is [first-filing](first-filing.md)'s.

## Done when

- A test carries out job 34's plan on a synthetic tree built from its fixture,
  with dry run off, and the tree ends in the layout its row of the fixtures
  table gives: film, sidecars, `raw/` with `disc.json`, nothing left behind.
- The test that nothing but the executor writes under the video root passes,
  and fails when a module is made to write there.
- `reelbarrow file` in the deployed pod, on job 34, reports every operation
  refused by dry run, and the share is unchanged.
