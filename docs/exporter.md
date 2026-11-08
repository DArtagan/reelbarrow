# The manifest exporter

`reelbarrow export-manifests` copies ARM's database out as one manifest per job,
which is how the service learns of ARM's jobs. Why it polls the database rather
than hooking ARM's notifications, and what intake may read from a manifest, are
in *The ARM manifest* in the [design](design.md). This page is how to run it.

```bash
reelbarrow export-manifests --db /root/db/arm.db --out /manifests
```

| option | default | |
|---|---|---|
| `--db` | required | ARM's `arm.db` |
| `--out` | `REELBARROW_MANIFEST_DIR` | the manifest directory, `import/automatic-ripping-machine/manifests/` on the share |
| `--interval` | 30 | seconds from the start of one pass to the start of the next |
| `--timeout` | 5 | seconds a pass waits on ARM's write lock before giving up until the next |
| `--once` | | one pass; exits 1 if it couldn't read the database or write the manifests |

It runs from reelbarrow's image, so exporter and reader are always the same
version. In Kubernetes it is a sidecar in ARM's pod, the only place ARM's
database volume can be mounted beside ARM.

## What a pass does

1. Opens the database with `mode=ro`, so SQLite refuses every write through the
   connection, and reads every `job` and `track` row in one read transaction.
   The `config` table, which holds ARM's API keys, is never read.
2. Builds each job's manifest and writes `job-<id>.json` only if it differs from
   the file there, by writing a hidden temporary file in the same directory and
   renaming it over the old one. A reader sees the old file or the new one,
   whole, and an unchanged job's file keeps its modification time.
3. Writes `exporter.json` last, the same way.

It never creates the manifest directory or the database: a missing mount fails
loudly rather than filling the container's own filesystem. It never deletes a
manifest. When a job's row disappears, deleted from ARM's UI, its manifest stays
and the exporter logs it once.

A pass that can't read the database (locked past `--timeout`, missing,
unreadable) or can't write to the share logs the error, writes nothing, and the
next pass tries again. A row holding a value JSON can't carry faithfully, such
as a boolean column holding 7, skips that job, not the pass, and is named in
`exporter.json`.

## The manifest

```json
{
  "schema": 1,
  "job": {"job_id": 7, "status": "success", "start_time": "2026-10-21T19:49:49.973701", "…": "…"},
  "tracks": [{"track_id": 31, "job_id": 7, "filename": "title_1.mkv", "ripped": true, "…": "…"}]
}
```

`job` holds every column of the job row and `tracks` every column of its track
rows, in `track_id` order, under the names ARM gives them. Columns are not
picked, so one ARM adds in a migration appears without a change here. The rows
are nested rather than spread at the top level so that no column can collide
with `schema`. Values keep ARM's meaning, typed by the column's declared type:
a `BOOLEAN` is `true` or `false` rather than SQLite's 0 or 1, and a `DATETIME`
is ISO 8601 without a zone, ARM's local time, exactly as stored. A null stays
null. [`tests/fixtures/manifests/dvd-movie.json`](../tests/fixtures/manifests/dvd-movie.json)
is a whole one, and a change to the shape changes it.

`schema` follows the stamp's rule (*The raw folder's stamp* in the design): a
field added leaves it at 1, and once reelbarrow's reader is deployed a field
removed or changed in meaning raises it.

## Liveness: `exporter.json`

```json
{"passed_at": "2026-11-08T21:30:00.123456+00:00", "version": "0.2.0", "jobs": 87, "skipped_jobs": []}
```

`passed_at` is the end of the last pass that read the database and wrote every
manifest that changed, in UTC. A pass that failed doesn't rewrite it, so a
`passed_at` older than two intervals means the exporter is stopped or failing,
which the service can't otherwise tell from no discs. `skipped_jobs` lists the
jobs the pass couldn't serialise. Intake reads only `job-*.json`.

## Mounts and permissions

The exporter needs two mounts:

- **ARM's database directory**, not just the file: SQLite looks beside the
  database for a journal.
- **The manifest directory** of the share, and nothing else of it. The exporter
  never mounts the library, which is why it is the one writer the executor's
  rule allows outside the executor, and only inside `--out`.

The process must be able to read `arm.db` and to create, write and rename files
in the manifest directory. Manifests are created mode 0666 less the umask, so a
service running as another user can read them on a filesystem that keeps modes.

### Journal mode

`mode=ro` reads a rollback-journal database, SQLite's default, from a read-only
mount. ARM 2.24.4's source sets no journal mode. Two cases need a
writable database directory, even with the connection read-only:

- **WAL mode**, where a reader uses the `-wal` and `-shm` files beside the
  database, and must be able to create them when ARM has none open.
- **A hot journal** left by a crash in the middle of a write, which the first
  connection must roll back. A read-only connection gets an error instead, and
  the exporter retries each pass until ARM's next write recovers it.

Not yet checked on the deployed database: its `PRAGMA journal_mode`, and so
whether the database volume can be mounted read-only.
