# arm-manifest-export: ARM's database, copied out as manifests

## Opening prompt

> Build `reelbarrow export-manifests`, which reads ARM's database read-only on
> an interval and writes `manifests/job-<id>.json` for every job, and prove it
> on a real disc. Read `todos/arm-manifest-export.md`, then *What ARM knows,
> and where* and *The ARM manifest* in `docs/design.md`. Nothing here has been
> written or run; every fact about ARM below was read from ARM `2.24.4`'s
> source, not exercised.

## Why it lives here (decided 2026-10-19)

The manifest is how reelbarrow learns of ARM's jobs, so what writes it ships
with reelbarrow and every user runs the same one. Will agreed with this split:

- **Here:** the exporter, the manifest's schema, and their tests.
- **In each deployment:** running it beside ARM, with ARM's database and the
  manifest directory mounted.

## Why an exporter, not a hook (decided 2026-11-08)

This spec was first written as `arm-manifest-hook`: a bash shim set as ARM's
`BASH_SCRIPT`, run on every notification, finding its job by `$PPID` = `job.pid`
and rewriting the manifest from the database. Reading more of ARM's source
showed it cannot record how a job ends:

- **ARM sets the final status after its last notification.** On success the
  last notification is `notify_exit()` near the end of `main()`, while the
  status is still `active`; `success` is set in `main.py`'s `else:` after
  `main()` returns and committed in its `finally:`, and nothing is notified
  after. On a fatal error `notify()` runs first and `status = fail`, `errors`
  and `stop_time` follow it. A job abandoned from ARM's UI is never notified at
  all: `abandon_job` writes a `Notifications` row directly. So every manifest
  the hook wrote would end at `active` or `transcoding`, and its done-when
  check could never pass.
- The hook also needed a bash shim, an environment variable naming the
  ripper's pid, and a dispatcher in every site that already uses
  `BASH_SCRIPT`, all to make the pid link work, and a separate export mode for
  past jobs.

Polling the database removes all of that, sees every status ARM commits, and is
one code path for past and new jobs. Offered the poller run as a sidecar from
reelbarrow's image, Will said: *"That sounds good, proceed"* (2026-11-08).

Don't reintroduce the hook to save the polling interval: whatever runs inside a
notification sees the job before ARM has finished with it. A ping for latency
is in *The ARM manifest*; it would trigger a pass, never replace one.

## What ARM gives (read from 2.24.4's source, not exercised)

- **The job row exists before "Found disc".** `setup()` adds it with status
  `active` (`main.py`, `database_adder(job)`), and `main()` calls
  `notify_entry()`, the "Found disc" notification, as its first step, before
  any rip.
- **Statuses** are `JobState` (`models/job.py`). `success` and `fail` are the
  only final ones. `active` means initialised *or* between stages (ARM sets it
  back after HandBrake), so it never means done.
- **A job whose ripper died stays unfinished in the database** until the next
  job's `setup()` runs `clean_old_jobs()`, which marks it `fail`. A pass reads
  what ARM has committed, so its manifest says the same until then.
- **`path` is the completed directory as ARM's container sees it**
  (`/root/video/completed/…`), set by `database_updater` before the files are
  moved, and set again if the title changes. It includes any `_<stage>`
  suffix.
- **`start_time` and `stop_time` are naive `datetime.now()`**, ARM's local
  time.
- **ARM's processes already share the database**: the UI and each ripper hold
  their own SQLAlchemy sessions on it. A reader taking a shared lock for a few
  milliseconds is one more of the same. Not checked: its journal mode (see
  *Design*).

## Design

- **A subcommand of reelbarrow's CLI**, `reelbarrow export-manifests --db <arm.db>
  --out <dir>`, looping every `--interval` seconds (30 to start), with `--once`
  for one pass. It is ordinary reelbarrow code, tested here and shipped in
  reelbarrow's image. It runs on Python 3.13, unlike ARM's container, which has
  3.10.
- **Each pass reads in one read transaction**: every job row and its track rows,
  so a manifest never mixes two states of a job. Open the database with
  `file:…?mode=ro` and a busy timeout, never for writing.
- **Write only what changed.** Build each job's manifest, compare it with the
  file already there, and replace the file only if they differ: write to a
  temporary file in the same directory, then `rename()`. The service scans that
  directory and must never read half a file, and an unchanged job leaves its
  file's modification time alone, so the service's "manifest changed" is real.
- **Never delete a manifest.** ARM's UI can delete a job's row. Its manifest
  stays, since a manifest that outlives ARM's records is why it's a file. Log
  the row's disappearance once.
- **Contents**, under a top-level `"schema": 1`, so intake can refuse a
  manifest it does not understand rather than misread it: every column of the
  `job` row, and of each of its `track` rows, as ARM holds them. Don't pick
  columns. `title_auto` and `title_manual` show a correction, `errors` why a job
  failed, and choosing now would guess at what a later spec needs. Never the
  `config` table, which holds API keys. Datetimes go out as ISO 8601 without a
  zone, as stored. Don't convert them: the exporter's zone needn't be ARM's.
  `ripped` is not "transcoded" (*The ARM manifest*). Don't reinterpret it here,
  so intake reads one meaning however the deployment sets it. The schema
  follows the stamp's rule (*The raw folder's stamp*): a field added leaves it
  at 1, and a field removed or changed in meaning raises it once reelbarrow's
  reader is deployed.
- **No raw folder, and no logs.** ARM's database records no raw path. The raw
  folder's stamp names its job, and intake joins the two on `job_id`. A
  Blu-ray's title map is in the stamp of every raw folder that holds the whole
  disc (*The raw folder's stamp*), so job logs needn't be read either.
- **Liveness.** If the exporter stops, no manifest changes, and nothing in the
  service can tell "no discs" from "no exporter". Each pass also rewrites
  `exporter.json` in the output directory, with the pass's time in UTC and
  reelbarrow's version. The service exports that time as a metric
  ([metrics](metrics.md)). Intake reads only `job-*.json`.
- **Fail loudly, and don't stop.** A pass that can't open or read the database
  (locked past the timeout, or missing) logs and tries again next interval. A
  row that can't be serialised logs its `job_id` and skips that job, not the
  pass.
- **Journal mode.** With ARM's default rollback journal, a `mode=ro`
  connection reads a database on a read-only mount. In WAL mode, or with a hot
  journal left by a crash, SQLite has to write beside the database, and a
  read-only mount fails. Check `PRAGMA journal_mode` on the real database in
  this session, and mount for whatever that needs. The connection stays `mode=ro`
  either way.
- **The library's write rule.** `AGENTS.md` lets only the executor write under
  the video root. The exporter is a separate process that never mounts the
  library. It writes only inside `--out`, and the test that holds the
  executor's line ([movie-filing](movie-filing.md)) allows this module's
  writes there and nowhere else.

## Tests

pytest against a SQLite database built from ARM `2.24.4`'s `job` and `track`
models, with synthetic rows. A real `arm.db` is never committed. Cover: a pass
over several jobs; a status change rewriting only that job's manifest; an
unchanged job's file untouched; a deleted row leaving its manifest; atomic
replacement (no reader sees a partial file); a database opened read-only, and
an attempt to write through that connection refused; a locked database, retried
next pass; `exporter.json` rewritten each pass; and the manifest's shape, held
by a fixture manifest in `tests/fixtures/`.

## The deployment half

Described here; the deployment repository's own spec carries it out. Its
*ARM's manifest hook* section, which describes the dispatcher, changes to:

- **A sidecar in ARM's pod**, running reelbarrow's image with
  `reelbarrow export-manifests`. It mounts ARM's database volume (the
  `openebs-hostpath` PVC on worker-1, `/root/db/arm.db` in ARM's container) and,
  of the share, only the manifest directory,
  `import/automatic-ripping-machine/manifests/`. Its image tag follows the same
  image policy as the service, so exporter and reader move together.
- **No dispatcher.** `BASH_SCRIPT` stays `arm-audio-handoff.sh`.
- **No one-off export.** The sidecar's first pass writes a manifest for every
  job in the database, 1–41 included.
- **uid.** The sidecar must read the database file and write the manifest
  directory. Check what owns both.

## Done when

- The tests pass, and the exporter's use is documented in `docs/`, including
  the mounts it needs and the journal-mode finding.
- The sidecar's first pass writes a manifest for every job in ARM's database,
  and those in the design's fixtures table have the titles and `crc_id`s the
  table gives. The failed ones (15–17, 30, 31, 40, 41) read `fail`.
- On a real disc insert, `job-<id>.json` appears within one interval of
  "Found disc", before the rip finishes. It is rewritten as the status moves,
  and ends at `success` (or `fail`) with `stop_time` set. Its job id matches
  ARM's UI.
- `exporter.json` on the share is never older than two intervals while the
  sidecar runs.
