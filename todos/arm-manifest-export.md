# arm-manifest-export: ARM's database, copied out as manifests

## Opening prompt

> `reelbarrow export-manifests` is built and tested; what remains is proving it
> on the cluster and a real disc. Read `todos/arm-manifest-export.md`, then
> `docs/exporter.md`. The sidecar is the deployment repository's to add, from
> the first release that ships the command; check that release is deployed
> before anything else.

## What is done (2026-11-08)

- **The exporter**, `src/reelbarrow/exporter.py`, with its tests in
  `tests/test_exporter.py` against a database shaped like the deployed one
  (`tests/arm_db.py`), and the manifest's shape held by
  `tests/fixtures/manifests/dvd-movie.json`. Its use, mounts and the
  journal-mode finding are in `docs/exporter.md`.
- **Read from the deployed ARM, read-only, 2026-11-08**, with ARM's own Python
  and a `mode=ro` connection: `PRAGMA journal_mode` is `delete`; SQLite is
  3.37.2; `arm.db` is `0:0` 0644 in a 0777 directory; the share is mounted in
  ARM's pod by `smb.csi.k8s.io` as CIFS with
  `uid=0,gid=0,file_mode=0755,dir_mode=0755`; `manifests/` does not exist yet.
  103 jobs, 1–103: 68 `success`, 34 `fail`, and 103 `ripping` at the time.
  Datetimes are stored as text (`2026-11-08 21:52:36.805910`), booleans as
  integers. The migrated schema puts `job.path` and `job.stage` after
  `pid_hash`, as bare `VARCHAR`, unlike the model; the test database follows the
  deployed one.

Will's decisions, kept so they aren't relitigated: the exporter, the manifest's
schema and their tests live here, and running it beside ARM is each
deployment's (2026-10-19). Polling the database rather than a notification hook,
run as a sidecar from reelbarrow's image: *"That sounds good, proceed"*
(2026-11-08). Don't reintroduce the hook to save the polling interval: whatever
runs inside a notification sees the job before ARM has finished with it (*What
ARM knows, and where* in the design).

## Not yet checked

- **Rename over an existing file on the share.** The exporter replaces a
  manifest with `os.replace()`. Over SMB2+ the Linux client renames with
  replace-if-exists, but if the server refuses (a reader holding the file open,
  say) the client falls back to unlinking the target and renaming. A reader
  would then briefly see no file, never a partial one. Not measured on this
  share. Check it with the sidecar's first rewrite of a manifest while the
  service reads.

## The deployment half

Carried out by the deployment repository's own spec; what has to change there:

- **A sidecar in ARM's pod**, from reelbarrow's image, running
  `reelbarrow export-manifests --db /root/db/arm.db --out <manifest dir>`. Its
  image tag follows the service's image policy, so exporter and reader move
  together.
- **Mounts:** ARM's database volume, the `db` subpath of
  `automatic-ripping-machine-pvc`, read-only, which the `delete` journal mode
  allows. Of the share, only `import/automatic-ripping-machine/manifests/`,
  which must be created first: the exporter refuses a missing directory rather
  than write into the container.
- **uid 0.** The share's CIFS mount in that pod is `uid=0` with 0755 modes,
  so no other uid can write the manifest directory. Running as root with a
  read-only root filesystem and every capability dropped is the narrow form
  of that. The alternative is a mount whose options name the image's uid 1000,
  which is a different PV from ARM's.
- **No dispatcher.** `BASH_SCRIPT` stays `arm-audio-handoff.sh`.
- **No one-off export.** The first pass writes a manifest for every job in the
  database, 1–41 included.
- **ARM rolls when its pod spec changes**, killing any job running. Merge the
  sidecar while ARM is idle.

## Done when

- The sidecar's first pass writes a manifest for every job in ARM's database,
  and those in the design's fixtures table have the titles and `crc_id`s the
  table gives. The failed ones (15–17, 30, 31, 40, 41) read `fail`.
- On a real disc insert, `job-<id>.json` appears within one interval of
  "Found disc", before the rip finishes. It is rewritten as the status moves,
  and ends at `success` (or `fail`) with `stop_time` set. Its job id matches
  ARM's UI.
- `exporter.json` on the share is never older than two intervals while the
  sidecar runs.
- The rename check above is measured and its result written into
  `docs/exporter.md`.

Then this spec is deleted, with a line in `docs/project_log.md`.
