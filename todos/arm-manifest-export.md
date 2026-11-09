# arm-manifest-export: ARM's jobs, copied out as manifests

## Opening prompt

> `reelbarrow arm-export-manifests` and the deployment's raw-copy record are
> built, deployed and running; what remains is proving them on the cluster and
> a real disc. Read `todos/arm-manifest-export.md`, then *The manifest* and
> *The raw copy's record* in `docs/design.md`, and `docs/exporter.md`. The
> deployment half is in the deployment repository's
> `todos/video-library-ingest.md`. Check which reelbarrow release the sidecar
> runs, and that the second `--arm-path` is in, before anything else.

## What is done (2026-11-08)

- **The manifest**, reelbarrow's own record of a unit of work (*The manifest*):
  `src/reelbarrow/manifest.py` holds it as pydantic models, which validate
  every manifest written and generate `docs/manifest.schema.json`. Twenty-one
  real jobs exported are its fixtures, one folder per case in
  `tests/fixtures/manifests/`, ARM's rows and raw-copy records beside the
  manifests made of them, with `tests/test_manifest.py` holding the design's
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
  once. The patch's tests run against real SQLAlchemy 2.0, in a uv
  environment that repository gained for them.
- **Read from the deployed ARM, read-only, 2026-11-08**: `PRAGMA journal_mode`
  is `delete`; SQLite 3.37.2; `arm.db` is `0:0` 0644 in a 0777 directory; the
  share is CIFS in ARM's pod with `uid=0,gid=0,file_mode=0755,dir_mode=0755`;
  `manifests/` doesn't exist; ARM's `TZ` is `Etc/UTC`; Flask-SQLAlchemy 3.1.1
  and SQLAlchemy 2.0.19 give the patch `db.text`. 103 jobs, every one with a
  `stage`, all distinct, each matching its stamp's. The migration's dry run
  would write 32 rows (jobs 7, 8, 23, 25, 27 and 76–103) and passed over none;
  its transcode paths were checked against five jobs' completed folders, and
  321 of its 329 skipped titles name the title kept for them, the other 8
  being play-alls whose parts say. ARM's `job_dupe_check` copied job 5's
  corrected identity onto jobs 23 and 27 by label (and onto 61).
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
  title has no transcode; `completed.folder.path` mirroring `raw.folder.path`;
  `mkv-titles`; the command `arm-export-manifests`.
- **From the review of pull request #12** (2026-11-09): absent means not
  recorded and null means none, kept; the backup's two checks stated
  separately, `raw.check`, not a `complete` with a null in it; JSON Schema,
  generated from pydantic models; ARM's times taken as UTC unless told
  otherwise; `wholes` folded into `titles`, one reason, `played_by` where
  structure doesn't say what plays a title (*"A+"*). Will, on `wholes`: *"It
  feels like something is being duplicated between `titles` and `wholes`"*:
  the reason, `kept` and the list each held which titles another plays.
- **`--arm-path ARM=SHARE`**, ARM's path and the folder's path on the share. A
  wrong turn worth not repeating: asked for *"a clear mapping
  `/path/in/arm=/path/in/reelbarrow`"*, it was built with reelbarrow's path on
  the right, which made the exporter take the service's
  `REELBARROW_VIDEO_ROOT` off it. Will: *"If feels like these concepts are
  beginning to collide."* They did: the sidecar had to keep a setting it
  doesn't own equal to the service's. With the share's path on the right each
  process knows only its own mount.
- **The raw-copy table holds the manifest's shape** (2026-11-09), asked *"is
  this the best form for that?"* of the stamp's vocabulary it had kept. The
  exporter translates ARM's paths and drops `handbrake_title`, the patch's own
  key, and nothing else; the stamp's vocabulary lives only in the one-off
  migration.
- **A feature ARM renamed is recorded from ARM's `main_feature` row**
  (2026-11-09), when one track has it and the folder holds one other `.mkv`:
  jobs 25, 27, 78 and 79.
- **Each transcode's final path recorded by the patch** as ARM moves it (*"go
  with your option #1, recording the path"*), not found by listing folders.
- **After filing the manifest is out of date, and stays so**: *"maybe that's
  fine and this file has done its job of getting us there."* The ledger and
  `disc.json` take over; a manifest that changes after filing goes to review.
- **ARM's `job_dupe_check` stays unpatched** (2026-11-09). Offered patching
  out its copying of an identity between jobs by label, Will: *"It can stay
  as-is for now."* The manifest marks what it copies `copied_from_earlier_job`.
- Approved as a whole: *"Yes, do all of the above: checks, design, and code."*

## Deployed (2026-11-09)

Each step confirmed with Will, with ARM idle:

- **reelbarrow 0.3.0**, the first release with `arm-export-manifests`.
- **ARM's patch**: its pod logged `applied raw-copy-code` with the other ten
  edits, and the patched modules compile under its Python 3.10.
- **The migration**: 32 rows, byte for byte its dry run; `integrity_check` ok.
- **The sidecar** (deployment pull request #37). Its first deploy crash-looped:
  the image's CMD is `reelbarrow serve` with no ENTRYPOINT, so `args` alone
  replaced the command, and the pod wasn't Ready, taking ARM's web UI off its
  Service, for about twenty minutes. Fixed with `command: [reelbarrow]`. A
  server-side dry run can't catch that; running the image's command can.

Its first pass wrote 96 of 103 manifests. The failed jobs read `failed`, and
the 32 raw folders recorded are on the share. It skipped seven, which this
branch fixes:

- **Jobs 1–3, 5 and 6** recorded paths under `/root/media/`: ARM mounted the
  same folder of the share there until 2026-04-20 (deployment commit
  `ec63698`). `--arm-path` is now given once per folder, and the deployment
  adds `/root/media=import/automatic-ripping-machine`.
- **Jobs 12 and 13** are audio CDs, whose `crc_id` is MusicBrainz's disc id.
  `crc64` is now a DVD's only.

## What is left

1. **Release** this branch's fix.
2. **The deployment adds the second `--arm-path`**, from that release; merging
   it rolls ARM's pod, so while ARM is idle.
3. The checks below.

## Not yet checked

- **A rename over an existing file on the share.** The exporter replaces a
  manifest with `os.replace()`. Over SMB2+ the Linux client renames with
  replace-if-exists, but if the server refuses, with a reader holding the file
  open say, the client falls back to unlinking the target and renaming. A
  reader would then briefly see no file, never a partial one. Measure it with
  the sidecar's first rewrite of a manifest while something reads it.
- **The patch's writes through ARM's session**, on a real job: the record
  appears at the start of the rip, `check` after the backup's checks, and
  each transcode's path as it moves.

## Done when

- The sidecar's first pass writes a manifest for every job in ARM's database,
  and those in the design's fixtures table have the titles and CRC64s the
  table gives. The failed ones (15–17, 30, 31, 40, 41) read `failed`. Jobs 7,
  8, 23, 25, 27 and 76 on have a `raw`, and its `folder` is on the share, but
  for 81, a Blu-ray killed before the stamp existed, which has none.
- On a real disc insert, its manifest appears within one interval of "Found
  disc", before the rip finishes, with both of `raw.check` `not_run`. It is
  rewritten as the job moves, and ends at `succeeded` (or `failed`) with
  `finish_time` set and both checks run. Each transcode it lists is at
  its path on the share. Its id's job number matches ARM's UI.
- `exporter.json` on the share is never older than two intervals while the
  sidecar runs.
- The rename check above is measured and its result written into
  `docs/exporter.md`.

Then this spec is deleted, with a line in `docs/project_log.md`.
