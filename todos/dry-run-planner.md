# dry-run-planner: plan every job, execute nothing

## Opening prompt

> Build reelbarrow's planner and run it, in dry run, over everything ARM has
> produced. Read `todos/dry-run-planner.md`, then *The cases*, *The service*
> (steps 1–6), *Confidence* and *Target layout* in `docs/design.md`. The
> fixtures table in *What is waiting* is the acceptance test: every row must
> match, or be corrected with evidence.

## Scope

Steps 1–6 of the pipeline in *The service*: intake, analyse, classify, identify,
plan, gate. Step 7, file, is [movie-filing](movie-filing.md).

- **Intake** reads a manifest and finds the job's completed directory by its
  `path` and its raw folder by the stamp carrying its `job_id`, never by
  matching names.
- **Classify** sorts each title into one of: feature, episode, play-all, extra,
  exact duplicate, other cut, other work. It pairs transcodes with raw by the
  raw's form, as *Confidence* (a transcode is raw title X) and the flowchart
  under *Identity* lay out: the stamp's title map confirmed by
  structure, structure alone where there is no map, and fingerprints only
  where structure can't decide. Job 79 is the case that has to go to review,
  or be decided by its map: featurette variants that share their clips. A
  Blu-ray without a map pairs by `analysis.bluray.handbrake_duration`, the
  transcode's length predicted from its playlist and clips (E36).
- **Identify films**: ARM's IMDb ID → TMDB, checked against the feature's runtime
  (±3% to start). TV episodes are left unresolved and planned as review; that is
  [episode-matching](episode-matching.md).
- **Plan**: a complete list of operations with their reasons, including leftover
  deletions, rendered in the layout of *Target layout*.
- **Gate**: automatic, review, or hold, per *Confidence*. A plan is all or
  nothing.
- **Record**: plans go into SQLite under `REELBARROW_DATA_DIR`, and the web UI
  lists them read-only. That record is the "collect data" half of the dry run
  (Will, 2026-10-18).

The service scans `REELBARROW_MANIFEST_DIR` on an interval and replans when a
manifest changes.

## Bindings from the design that are easy to miss

- Choosing the best copy never uses size or bitrate (*Correction: the Rescuers
  "duplicate"*).
- Library names come from TMDB and must be folded to Latin-1 the way ARM's
  title hook does in the deployment, until the filename-charset migration
  lands. A name the share would reject with `EIO` is a
  planning error to catch here, not at filing time.
- The thresholds are starting points, and the evaluation sets them.
- Every job in the fixtures table predates the stamp (*The raw folder's stamp*),
  so the table exercises only fingerprint pairing. The stamped path needs a case
  of its own. Job 76, *Pinky and the Brain* D2, is the first stamped DVD, and
  job 75 ripped the same disc the day before without a stamp, so the two give
  both paths on one disc. Job 76's title map was filled in after the job, and
  matches job 77's, a re-rip of the same disc that wrote its own.
- A stamp's `duplicates` (*The raw folder's stamp*) means a title can be absent
  from `completed/` on purpose. Read it before calling a job's output
  incomplete. Downton Abbey gives both paths on one series: job 80 (D1) predates
  `duplicates` and transcoded its 207-minute play-all, and job 83 (D2) skipped
  its 157-minute one and recorded the episodes' starts. Its first movie-disc
  case, a whole kept and its parts skipped, is the *Robin Hood* bonus DVD's
  re-rip, which hasn't run as of 2026-10-26.
- **Where no stamp's `duplicates` decided it, the planner decides wholes and
  parts itself, by the deployment's rule** (Will, 2026-10-28; *Confidence*, which
  of a whole and its parts is kept). Port the decision from
  `_arm_duplicates` in the deployment's ARM patches, its thresholds and its
  final pass that unskips until every skipped title is played by those kept,
  with its tests as the model. The measurements are already here:
  `analysis.segments` over `bluray_playlists` and `dvd_structure`'s cells
  (*Title identity* 4), checked against job 83's recorded result. The cases,
  one per path: job 80 (Blu-ray, before `duplicates`, its play-all
  transcoded) and job 76 (a DVD image whose stamp predates `duplicates`; disc
  title 1 plays titles 4–9) by structure; *Robin Hood* job 36 and Tweety by
  fingerprint, since only MKVs survive. Job 36 has to keep `E1`'s transcode and
  drop those of `E2`–`E4`. Placing a part by fingerprint within the 1 s a
  chapter join allows is unmeasured; measure it on job 36 first.
- **A DVD whole's `start` is in playback seconds once the deployment scales
  it** (Will, 2026-10-28: the deployment scales, not the reader). Until then
  its ARM places DVD parts from lsdvd's unscaled lengths, 0.1% early on NTSC.
  The fix is in the deployment's disc-ripping review and, run over job 76's
  real lsdvd output, gives the starts `analysis.segments` does. No stamp on
  the share has a DVD whole yet, so none needs rewriting, provided the fix is
  deployed before the *Robin Hood* bonus DVD's re-rip. Check that it was
  before trusting that stamp's starts: they should sit within 0.25 s of its
  transcode's chapters.
- A movie's feature arrives as `title_N.mkv` above `extras/` once the
  deployment stops ARM renaming it, and as `<Title (Year)>.mkv` before. Intake
  takes neither name, nor the placement, as the identification.

## Secrets

A TMDB API key (a free personal key) is the first secret the service needs. Add
it to reelbarrow's encrypted secret in the deployment repository, read it from
the environment, and keep it out of logs.

## Done when

- Layer-1 tests drive the planner over `tests/fixtures/` and assert the outcome
  for every row of the fixtures table.
- The deployed pod, in dry run, has planned every job under `completed/`, and
  a row-by-row comparison with the table matches. Where it does not, either the
  code or the table is corrected, with the evidence written into the design.
- The share is unchanged: the mount is read-only, and the ledger records no
  executed operation.
