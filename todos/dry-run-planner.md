# dry-run-planner: plan every job, execute nothing

## Opening prompt

> Build reelbarrow's planner and run it, in dry run, over everything ARM has
> produced, capturing each case's fixture as its rule is written. Read
> `todos/dry-run-planner.md`, then *The cases*, *The service* (steps 1–6),
> *Confidence*, *Target layout* and *Testing* (layer 1) in `docs/design.md`.
> The fixtures table in *What is waiting* is the acceptance test: every row
> must match, or be corrected with evidence. Everything in this session is
> read-only on the share.

## Scope

Steps 1–6 of the pipeline in *The service*: intake, analyse, classify, identify,
plan, gate. Step 7, file, is [movie-filing](movie-filing.md).

- **`reelbarrow analyse <path> --out <dir>`** comes first. It runs the
  analysis layer over a job's folders in the pod and writes what it measured,
  and its output is the fixtures' form (*Fixtures, case by case*), so the
  planner reads the same thing from a fixture as from the share.

- **Intake** reads a manifest and finds the job's completed and raw folders by
  the paths it records (*The manifest*), checking they are there, never by
  matching names.
- **Classify** sorts each title into one of: feature, episode, play-all, extra,
  exact duplicate, other cut, other work. It pairs transcodes with raw by the
  raw's form, as *Confidence* (a transcode is raw title X) and the flowchart
  under *Identity* lay out: the manifest's `titles` confirmed by
  structure, structure alone where there is no map, and fingerprints only
  where structure can't decide. Job 79 is the case that has to go to review,
  or be decided by its map: featurette variants that share their clips. A
  Blu-ray without a map pairs by `analysis.bluray.Playlist.handbrake_duration`, the
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
- Every job in the fixtures table predates the raw copy's record (*The raw
  copy's record*), so the table exercises only fingerprint pairing. The
  recorded path needs a case of its own. Job 76, *Pinky and the Brain* D2, is
  the first DVD whose raw copy is recorded, and job 75 ripped the same disc the
  day before without one, so the two give both paths on one disc. Job 76's
  title map was recorded after the job, and matches job 77's, a re-rip of the
  same disc that recorded its own.
- A title's `reason` (*The raw copy's record*) means it can be absent from
  `completed/` on purpose. Read it before calling a job's output incomplete.
  Downton Abbey gives both paths on one series: job 80 (D1) predates skipped
  titles being recorded and transcoded its 207-minute play-all, and job 83 (D2) skipped
  its 157-minute one and recorded the episodes' starts. Its first movie-disc
  case, a whole kept and its parts skipped, is job 87, the *Robin Hood* bonus
  DVD's re-rip: it transcoded disc title 1's documentary and the two
  featurettes, and skipped titles 2–4.
- **Where the manifest's titles weren't compared (no `raw.titles_compared`),
  the planner decides wholes and
  parts itself, by the deployment's rule** (Will, 2026-10-28; *Confidence*, which
  of a whole and its parts is kept). Port the decision from
  `_arm_duplicates` in the deployment's ARM patches, its thresholds and its
  final pass that unskips until every skipped title is played by those kept,
  with its tests as the model. The measurements are already here:
  `analysis.segments` over `bluray.playlists` and `dvd.structure`'s cells
  (*Title identity* 4), checked against job 83's recorded result. The cases,
  one per path: job 80 (Blu-ray, before titles were compared, its play-all
  transcoded) and job 76 (a DVD image whose record predates comparing; disc
  title 1 plays titles 4–9) by structure; *Robin Hood* job 36 and Tweety by
  fingerprint, since only MKVs survive. Job 36 has to keep `E1`'s transcode and
  drop those of `E2`–`E4`, which is what job 87 recorded for the same disc.
  Placing a part by fingerprint within the 1 s a
  chapter join allows is unmeasured; measure it on job 36 first.
- **A DVD whole's `start` is in playback seconds** (Will, 2026-10-28: the
  deployment scales, not the reader). lsdvd's unscaled lengths would place
  parts 0.1% early on NTSC. Job 87, the first record with a DVD whole, ran
  with the deployment's scaling: its starts equal its whole's MKV chapters to
  the millisecond and sit within 0.07 s of its transcode's.
- A movie's feature arrives as `title_N.mkv` above `extras/` since the
  deployment stopped ARM renaming it, and as `<Title (Year)>.mkv` before. Intake
  takes neither name, nor the placement, as the identification.

## Fixtures, case by case

This spec captures the layer-1 fixtures (*Testing* in the design) one case at a
time: capture the case from the share, write its row of the fixtures table as a
failing test, then write the rule that passes it. They were a spec of their own,
`fixtures`, captured ahead of the planner. Will agreed to fold it in here
(2026-11-09: *"I agree."*), because a capture made before the rules that read
it has to guess at what they need, and at the shape of the loader. The
manifest's fields were chosen by the same principle, each traced to a rule
that reads it; Will, 2026-11-08: *"An interface that includes everything is
both fragile and wasteful."*

- **Capture what a rule reads, no more.** The candidates are ffprobe JSON,
  video MD5s, fingerprints, Blu-ray hashes, a DVD image's
  `lsdvd -c -d -v -Oy` output, and a Blu-ray's playlists and clips' entry
  points as read by `bluray.playlists` and `bluray.clips`. A case that no rule
  reads one of these for doesn't capture it.
- **Run it in the pod, copy out only results.** Media streamed through
  `kubectl exec` ran at 17.6 MB/s (E25) and truncated two fingerprints (E30).
  Compare a checksum taken in the pod with one taken after the copy, as E30
  did.
- **Check each capture against a fresh listing** from the pod: its file count
  and durations. That catches a truncated capture.
- **Named for the case, under `tests/fixtures/<case>/`** (*Testing*, layer 1),
  with a loader that presents a job to the planner as intake would see it on
  the share. A job's manifest is the one already frozen in
  `tests/fixtures/manifests/`, where there is one, not a second copy.
- **The empty skeleton directories are fixtures too, as directory listings.**
  The planner has to classify them as leftovers.
- **The cases outside the table** that *Bindings* names (jobs 75–77, 80, 83, 87
  and 36) are captured the same way, when their rule is written.
- **No Whisper transcripts.** The planner leaves episodes to review and
  doesn't read them; whether they are committed is settled in
  [episode-matching](episode-matching.md).
- **Inputs**: the manifests that
  [arm-manifest-export](arm-manifest-export.md)'s sidecar writes into
  `import/automatic-ripping-machine/manifests/`. If they aren't there yet, that
  step comes first.

## Secrets

A TMDB API key (a free personal key) is the first secret the service needs. Add
it to reelbarrow's encrypted secret in the deployment repository, read it from
the environment, and keep it out of logs.

## Done when

- Layer-1 tests drive the planner over `tests/fixtures/` and assert the outcome
  for every row of the fixtures table.
- Each fixture's file count and durations matched a fresh listing from the pod
  when it was captured.
- The deployed pod, in dry run, has planned every job under `completed/`, and
  a row-by-row comparison with the table matches. Where it does not, either the
  code or the table is corrected, with the evidence written into the design.
- The share is unchanged: the mount is read-only, and the ledger records no
  executed operation.
