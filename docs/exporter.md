# The manifest exporter

`reelbarrow arm-export-manifests` copies ARM's jobs out of its database as
manifests, which is how the service learns of them. What a manifest says, and
why the exporter polls ARM's database rather than hooking its notifications,
are *The manifest* and *The raw copy's record* in the [design](design.md). This
page is how to run it.

```bash
reelbarrow arm-export-manifests --db /root/db/arm.db --out /manifests \
  --arm-path /root/video=/video/import/automatic-ripping-machine
```

| option | default | |
|---|---|---|
| `--db` | required | ARM's `arm.db` |
| `--arm-path` | required | `ARM=REELBARROW`: one folder, as ARM's container mounts it and as reelbarrow does |
| `--arm-timezone` | `Etc/UTC` | the IANA zone ARM's container runs in, whose local time ARM stores |
| `--out` | `REELBARROW_MANIFEST_DIR` | the manifest directory, `import/automatic-ripping-machine/manifests/` on the share |
| `--interval` | 30 | seconds from the start of one pass to the start of the next |
| `--timeout` | 5 | seconds a pass waits on ARM's write lock before giving up until the next |
| `--once` | | one pass; exits 1 if it couldn't read the database or write the manifests |

### `--arm-path`

ARM records every path as its own container sees it, and the exporter itself
never sees those files, so it has to be told where they are on the share. In
the deployment this was built for, ARM's pod mounts only one folder of the
share, `import/automatic-ripping-machine`, at `/root/video`, while reelbarrow
mounts the whole share at `/video`. So one folder is `/root/video` to ARM and
`/video/import/automatic-ripping-machine` to reelbarrow, which is what the
option says:

```
--arm-path /root/video=/video/import/automatic-ripping-machine
```

ARM's `/root/video/completed/movies/X` then goes into the manifest as
`import/automatic-ripping-machine/completed/movies/X`: the right-hand side with
reelbarrow's video root, `REELBARROW_VIDEO_ROOT`, taken off, so that it is a
path from the share's root that no mount appears in. The service, reading it,
puts its own video root back. The right-hand side must be inside that video
root, and the exporter runs from reelbarrow's image, so it has the service's
default, `/video`; a deployment that changes one changes both. It has no
default itself, because no value is right everywhere, and a wrong one makes
plausible paths rather than failing.

### `--arm-timezone`

ARM stores its local time without a zone, and its image runs in `Etc/UTC`
unless its `TZ` is set. A deployment that sets ARM's `TZ` passes the same here.

It runs from reelbarrow's image, so exporter and reader are always the same
version. In Kubernetes it is a sidecar in ARM's pod, the only place ARM's
database volume can be mounted beside ARM.

## What a pass does

1. Opens the database with `mode=ro`, so SQLite refuses every write through the
   connection, and reads in one read transaction the `job` columns it needs and
   the deployment's `reelbarrow_raw_copy` table, if there is one. The `track`
   and `config` tables are never read; `config` holds ARM's API keys.
2. Builds each job's manifest and writes `manifest-arm-<job_id>-<stage>.json`
   only if it differs from the file there, by writing a hidden temporary file in
   the same directory and renaming it over the old one. A reader sees the old
   file or the new one, whole, and an unchanged job's file keeps its
   modification time.
3. Writes `exporter.json` last, the same way.

It never creates the manifest directory or the database: a missing mount fails
loudly rather than filling the container's own filesystem. It never deletes a
manifest. When a job's row disappears, deleted from ARM's UI, its manifest stays
and the exporter logs it once. A recreated database starts its job ids again
from 1, but not its stages, so its manifests are new files.

A pass that can't read the database (locked past `--timeout`, missing,
unreadable, or lacking a `job` column the exporter reads, say after an ARM
upgrade) or can't write to the share logs the error, writes nothing, and the
next pass tries again. A job it can't carry faithfully skips that job, not the
pass, and is named in `exporter.json`: a time that doesn't parse, a raw-copy
record it doesn't understand, a path outside `--arm-path`, or a manifest the
model refuses, one that would contradict itself.

Without the deployment's patch there is no `reelbarrow_raw_copy`, and each
manifest has no `raw` or `titles`: not recorded, which intake reads
as unknown.

[`tests/fixtures/manifests/`](../tests/fixtures/manifests/) holds real jobs
exported, each named for its case.

## Liveness: `exporter.json`

```json
{"passed_at": "2026-11-08T21:30:00.123456+00:00", "version": "0.2.0", "jobs": 103, "skipped_jobs": []}
```

`passed_at` is the end of the last pass that read the database and wrote every
manifest that changed, in UTC. A pass that failed doesn't rewrite it, so a
`passed_at` older than two intervals means the exporter is stopped or failing,
which the service can't otherwise tell from no discs. `skipped_jobs` lists, by
ARM's job id, the jobs the pass couldn't export. Intake reads only
`manifest-*.json`.

## Mounts and permissions

The exporter needs two mounts:

- **ARM's database directory**, not just the file: SQLite looks beside the
  database for a journal.
- **The manifest directory** of the share, and nothing else of it. The exporter
  never mounts the library, which is why it is the one writer the executor's
  rule allows outside the executor, and only inside `--out`.

The process must be able to read `arm.db` and to create, write and rename files
in the manifest directory, which must exist before the first pass. Manifests are
created mode 0666 less the umask, so a service running as another user can read
them on a filesystem that keeps modes. A CIFS mount doesn't: the client checks
every access against the owner and modes in its mount options, so the exporter
must run as the mount's `uid`, or the mount must name the exporter's.

In the deployment this was built for, ARM runs as root and its database is
`0:0`, mode 0644, in a directory open to all, so any uid can read it. The share
is mounted `uid=0,gid=0,file_mode=0755,dir_mode=0755` in ARM's pod, so a
sidecar on that volume writes the manifest directory only as uid 0.

### Journal mode

`mode=ro` reads a rollback-journal database, SQLite's default, from a read-only
mount. ARM 2.24.4's source sets no journal mode. Two cases need a writable
database directory, even with the connection read-only:

- **WAL mode**, where a reader uses the `-wal` and `-shm` files beside the
  database, and must be able to create them when ARM has none open.
- **A hot journal** left by a crash in the middle of a write, which the first
  connection must roll back. A read-only connection gets an error instead, and
  the exporter retries each pass until ARM's next write recovers it.

The deployed database reads `PRAGMA journal_mode` `delete`, a rollback journal,
so its volume can be mounted read-only.
