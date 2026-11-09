# arm-manifest-export: ARM's jobs, copied out as manifests

## Opening prompt

> `reelbarrow export-manifests` and the deployment's raw-copy record are built
> and tested; what remains is deploying them and proving them on the cluster
> and a real disc. Read `todos/arm-manifest-export.md`, then *The manifest* and
> *The raw copy's record* in `docs/design.md`, and `docs/exporter.md`. The
> deployment half is in the deployment repository's
> `todos/video-library-ingest.md`. Check which reelbarrow release is deployed,
> and whether ARM's patch and the migration have gone in, before anything else.

## What is done (2026-11-08)

- **The manifest**, reelbarrow's own record of a unit of work (*The manifest*):
  `src/reelbarrow/manifest.py` holds its schema, file name, share reference
  and vocabularies. Twenty real jobs exported are its fixtures,
  `tests/fixtures/manifests/`, from their rows and raw-copy records in
  `tests/fixtures/arm/`, with `tests/test_manifest.py` holding the design's
  rules against them.
- **The exporter**, `src/reelbarrow/exporter.py`, ARM's adapter to it, tested
  in `tests/test_exporter.py` against a database shaped like the deployed one
  (`tests/arm_db.py`). Its use, mounts and the journal-mode finding are in
  `docs/exporter.md`.
- **The deployment's half, on its `video-library-ingest` branch** (its pull
  request #35): the patch records each job's raw copy in
  `reelbarrow_raw_copy` in ARM's database instead of `arm-job.json`, including
  each transcode's final path as ARM moves it; and
  `tools/arm-stamps/raw_copies.py` moves the existing stamps into that table
  once.
- **Read from the deployed ARM, read-only, 2026-11-08**: `PRAGMA journal_mode`
  is `delete`; SQLite 3.37.2; `arm.db` is `0:0` 0644 in a 0777 directory; the
  share is CIFS in ARM's pod with `uid=0,gid=0,file_mode=0755,dir_mode=0755`;
  `manifests/` doesn't exist; ARM's `TZ` is `Etc/UTC`; Flask-SQLAlchemy 3.1.1
  and SQLAlchemy 2.0.19 give the patch `db.text`. 103 jobs, every one with a
  `stage`, all distinct, each matching its stamp's. The migration's dry run
  would write 32 rows (jobs 7, 8, 23, 25, 27 and 76–103) and passed over none;
  its transcode paths were checked against five jobs' completed folders.
- **Read from ARM 2.24.4's source**: its migrations touch only the tables they
  name and rebuild `job` with `batch_alter_table`, so the patch's table
  survives an upgrade and declares no foreign key; ARM moves every transcode
  through `utils.move_files`.

## Decisions, so they aren't relitigated

- The exporter, the manifest's schema and their tests live here; running it
  beside ARM is each deployment's (2026-10-19).
- Polling ARM's database rather than a notification hook, run as a sidecar
  from reelbarrow's image: *"That sounds good, proceed"* (2026-11-08). Don't
  reintroduce the hook to save the polling interval: whatever runs inside a
  notification sees the job before ARM has finished with it.
- **Not every column** (2026-11-08): *"An interface that includes everything
  is both fragile and wasteful."* The manifest is in reelbarrow's vocabulary,
  not ARM's, and the exporter is the one place that knows ARM's schema. Every
  field is traced to a rule that reads it.
- **One file, not a manifest and a stamp.** Will: *"Matters having to do with
  the stamp are not a call for a different spec, they're for us to resolve
  right now - in this session"*, and asked whether the two could be condensed.
  They can, because every job of interest has its raw copy recorded: *"For the
  time being, let's assume that pre-76 DVD jobs will be re-ripped or matched up
  (raw to completed) in another manner."* The patch records into ARM's
  database, and the stamp file is retired. ARM's track rows are dropped,
  MakeMKV's with them: they matter only for those pre-76 DVD jobs.
- **Every path whole, and one way of holding one**: *"there needs to be
  standardization & encapsulation of these fields"*; a share reference,
  relative to the share's root, so no process's mounts appear in a manifest.
- **Names**: `start_time` and `finish_time`; `reason` for why a claim holds or a
  title has no transcode; `completed.folder.path` mirroring `raw.folder.path`.
- **Each transcode's final path recorded by the patch** as ARM moves it (*"go
  with your option #1, recording the path"*), not found by listing folders.
- **After filing the manifest is out of date, and stays so**: *"maybe that's
  fine and this file has done its job of getting us there."* The ledger and
  `disc.json` take over; a manifest that changes after filing goes to review.
- Approved as a whole: *"Yes, do all of the above: checks, design, and code."*

## What is left, in order

Each step that changes the cluster or the share is confirmed with Will first.

1. **Release reelbarrow**: merge this pull request, then its release pull
   request, so the image has `export-manifests`.
2. **Deploy ARM's patch** (the deployment's pull request). It changes ARM's
   pod, and the `Recreate` strategy kills any job running: merge it while ARM
   is idle, then check in the container, not the ConfigMap, that
   `arm-source-patches.py` logged `applied raw-copy-code`.
3. **Run the migration** in ARM's pod, dry run first, then `--write`. It is a
   write to ARM's live database, adding rows to a table no ARM code reads;
   check the dry run's count and passed-over list again, as jobs will have run
   since 2026-11-08.
4. **Add the sidecar** in ARM's pod, from the first release with the command.
   What it needs is in the deployment's spec.

## Not yet checked

- **A rename over an existing file on the share.** The exporter replaces a
  manifest with `os.replace()`. Over SMB2+ the Linux client renames with
  replace-if-exists, but if the server refuses, with a reader holding the file
  open say, the client falls back to unlinking the target and renaming. A
  reader would then briefly see no file, never a partial one. Measure it with
  the sidecar's first rewrite of a manifest while something reads it.
- **The patch's writes through ARM's session**, on a real job: the record
  appears at the start of the rip, `complete` after the backup's check, and
  each transcode's path as it moves.

## Done when

- The sidecar's first pass writes a manifest for every job in ARM's database,
  and those in the design's fixtures table have the titles and CRC64s the
  table gives. The failed ones (15–17, 30, 31, 40, 41) read `failed`. Jobs 7,
  8, 23, 25, 27 and 76 on have a `raw`, and its `folder` is on the share.
- On a real disc insert, its manifest appears within one interval of "Found
  disc", before the rip finishes, with `raw.complete` `not_checked`. It is
  rewritten as the job moves, and ends at `succeeded` (or `failed`) with
  `finish_time` set and `raw.complete` checked. Each transcode it lists is at
  its path on the share. Its id's job number matches ARM's UI.
- `exporter.json` on the share is never older than two intervals while the
  sidecar runs.
- The rename check above is measured and its result written into
  `docs/exporter.md`.

Then this spec is deleted, with a line in `docs/project_log.md`.
