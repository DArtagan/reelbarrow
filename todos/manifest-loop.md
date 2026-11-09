# manifest-loop: every manifest, in any order

## Opening prompt

> Widen reelbarrow's planner from one manifest to every manifest on the share,
> case by case from the simplest, so that every row of the fixtures table
> plans and gates as the table says, whatever order the manifests are taken
> in. Read `todos/manifest-loop.md`, then *The cases*, *The service* (*Any
> order* especially), *Confidence* and *Target layout* in `docs/design.md`.
> Dry run stays on, and everything in this session is read-only on the share.

## Why

The third of the steps in [README](README.md): the loop over every manifest.
It is where *Any order* in the design has to be earned. Will: *"the rules
should ensure that manifests can be processable in any order, with the library
eventually being filled with the best results."* Each plan is still made from
one manifest and the library as it stands. *The Hallelujah Trail* will already
be filed by [first-filing](first-filing.md), so the plans of its failed jobs
15–17 meet a library that holds it, which is the property under test.

## Scope

- **`reelbarrow plan --all`** plans every manifest in the manifest directory
  and prints each plan's gate. It records nothing; the inbox is
  [plan-inbox](plan-inbox.md).
- **The cases, simplest first**, each with its fixture captured as
  [single-manifest-plan](single-manifest-plan.md)'s *Fixtures, case by case*
  says, its row as a failing test, then the rule:
  1. The other films the table files automatically: *Those Daring Young Men…*
     job 34 (film only), *The Great Race* job 29 (film and one extra), *The
     Polar Express* job 25 (film, three extras, and its raw paired by
     fingerprint with the misnamed Mary-Kate folder, the 0.4 GB
     `raw/The-Polar-Express` a leftover).
  2. Manifests with nothing to file: failed jobs 15–17 beside job 18, and the
     empty skeletons (jobs 2, 3, 19, 38, 40, 41…), captured as directory
     listings, since the planner has to classify them as leftovers. The
     matching `raw/` entry decides whether anything survives
     (`raw/Le Mans_177654944116/B1_t00.mkv` does).
  3. One disc, several jobs: *The Polar Express* job 24, the same disc
     misidentified; *The Rescuers* jobs 5, 7, 8 and 23 beside job 27; Tweety
     job 33, byte-identical to job 22.
  4. The rows that go to review or hold, which must plan correctly even though
     nothing files them yet: *Field of Dreams*, both *Robin Hood* jobs, *The
     Rescuers*' second film, *Shrek the Third*'s fold, *Around the World in 80
     Days* (hold until disc 2), and Tweety (review until
     [episode-matching](episode-matching.md)).
  5. The cases outside the table that the bindings below name: jobs 75–77,
     79, 80, 83, 87 and 36.
- **Classify** in full: feature, episode, play-all, extra, exact duplicate,
  other cut, other work. It pairs transcodes with raw by the raw's form, as
  *Confidence* (a transcode is raw title X) and the flowchart under *Identity*
  lay out: the manifest's `titles` confirmed by structure, structure alone
  where there is no map, and fingerprints only where structure can't decide.
  Job 79 is the case that has to go to review, or be decided by its map:
  featurette variants that share their clips. A Blu-ray without a map pairs by
  `analysis.bluray.Playlist.handbrake_duration`, the transcode's length
  predicted from its playlist and clips (E36).
- **Identify films** as single-manifest-plan does. TV episodes are left
  unresolved and planned as review.

## Bindings from the design that are easy to miss

- Choosing the best copy never uses size or bitrate (*Correction: the Rescuers
  "duplicate"*).
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
  titles being recorded and transcoded its 207-minute play-all, and job 83 (D2)
  skipped its 157-minute one and recorded the episodes' starts. Its first
  movie-disc case, a whole kept and its parts skipped, is job 87, the *Robin
  Hood* bonus DVD's re-rip: it transcoded disc title 1's documentary and the
  two featurettes, and skipped titles 2–4.
- **Where the manifest's titles weren't compared (no `raw.titles_compared`),
  the planner decides wholes and parts itself, by the deployment's rule**
  (Will, 2026-10-28; *Confidence*, which of a whole and its parts is kept).
  Port the decision from `_arm_duplicates` in the deployment's ARM patches,
  its thresholds and its final pass that unskips until every skipped title is
  played by those kept, with its tests as the model. The measurements are
  already here: `analysis.segments` over `bluray.playlists` and
  `dvd.structure`'s cells (*Title identity* 4), checked against job 83's
  recorded result. The cases, one per path: job 80 (Blu-ray, before titles
  were compared, its play-all transcoded) and job 76 (a DVD image whose record
  predates comparing; disc title 1 plays titles 4–9) by structure; *Robin
  Hood* job 36 and Tweety by fingerprint, since only MKVs survive. Job 36 has
  to keep `E1`'s transcode and drop those of `E2`–`E4`, which is what job 87
  recorded for the same disc. Placing a part by fingerprint within the 1 s a
  chapter join allows is unmeasured; measure it on job 36 first.
- **A DVD whole's `start` is in playback seconds** (Will, 2026-10-28: the
  deployment scales, not the reader). lsdvd's unscaled lengths would place
  parts 0.1% early on NTSC. Job 87, the first record with a DVD whole, ran
  with the deployment's scaling: its starts equal its whole's MKV chapters to
  the millisecond and sit within 0.07 s of its transcode's.

## Needs

Manifests for jobs 1–6, which [arm-manifest-export](arm-manifest-export.md)'s
sidecar skips until it maps ARM's older `/root/media` paths. Jobs 2, 3 and 5
are rows of the fixtures table.

## Done when

- Layer-1 tests assert every row of the fixtures table from its fixtures.
- Each fixture's file count and durations matched a fresh listing from the pod
  when it was captured.
- A layer-1 test plans and carries out the table's manifests on a synthetic
  tree in several orders, shuffled, and every order ends in the same library.
- `reelbarrow plan --all` in the deployed pod has planned every manifest on
  the share, and a row-by-row comparison with the table matches. Where it does
  not, either the code or the table is corrected, with the evidence written
  into the design.
- The share is unchanged: the mount is read-only.
