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
  stamp's title map where there is one, otherwise by fingerprint.
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
