# fixtures: freeze the fixtures table's jobs into test data

## Opening prompt

> Capture frozen fixtures for every job in the fixtures table of
> `docs/design.md` (*What is waiting*), using reelbarrow's analysis layer
> running in the deployed dry-run pod against the real share. Read
> `todos/fixtures.md`. Everything in this session is read-only on the share.

## Why

Layer 1 of *Testing* runs every commit on fixtures derived from the media, not
the media, so CI never needs the share. This step produces them, once, for the
jobs that form the acceptance test.

## Inputs

- **ARM manifests for jobs 1–41.** The first pass of
  [arm-manifest-export](arm-manifest-export.md)'s exporter writes them, with
  every other job's, into `import/automatic-ripping-machine/manifests/`. If they
  are not there yet, that step comes first.
- **The share, read through the reelbarrow pod.** Do not stream media through
  `kubectl exec`: it ran at 17.6 MB/s (E25) and truncated two fingerprints
  (E30). Run the analysis inside the pod, which mounts the share directly, and
  copy out only the results, comparing a checksum taken in the pod with one
  taken after the copy. E30 copied four fingerprints out that way, verified.

## What to capture, per job

ffprobe JSON for every file in its completed and transcode directories and its
raw candidates; video MD5s; fingerprints; Blu-ray hashes; what each raw title
plays (*Title identity* 4), as a DVD image's `lsdvd -c -d -v -Oy` output and a
Blu-ray's playlists read by `bluray.playlists` and its clips' entry points by
`bluray.clips`, as JSON, which is all a decision needs of them; and the
manifest, which carries the raw copy's record where there is one. Store them under `tests/fixtures/<case>/`, named for the case as
*Testing*, layer 1, in the design says, in a layout the planner can load as if
it were the share.

Twenty-one manifests are frozen already in `tests/fixtures/manifests/`, a
folder per case holding a real job's row and raw-copy record (`arm-db.json`)
and the manifest exported from them, with the contract test that holds them:
among them
*The Rescuers* job 27, *The Polar Express* job 25 and *The Hallelujah Trail*
jobs 15 and 18 of the fixtures table, and job 87, the *Robin Hood* bonus DVD's
re-rip. A job's own fixture copies its manifest from there rather than
freezing a second one.

A `reelbarrow analyse <path> --out <dir>` command that does this in the pod is
probably the right shape, and the planner's own intake will want it anyway.

## Decisions for this session

- **What a public repository may hold.** ffprobe JSON and hashes are metadata.
  Fingerprints are settled: committed, for the reason under *Testing*, layer 1,
  in the design, and `tests/fixtures/fingerprints/` already holds four: Robin
  Hood's two cuts from job 35 and The Rescuers' two films from job 27. Will
  asked on PR #5 whether to pivot to the Blender films in the library (Sintel,
  Big Buck Bunny) and chose to keep these (2026-11-05), for the reason the
  design gives. Whisper transcripts of copyrighted programmes are
  text excerpts. Settle whether they are committed whole, trimmed, or kept out
  of git and fetched for evaluations only, and record the reason here.
- **Fixtures are named for their cases.** Will, on PR #5: *"Given that the
  source of these jobs will be disappearing, maybe we should rename these
  fixture files to the test cases they actually represent. Giving this repo a
  clean abstration about what the files mean to it, not where they came
  from."*
- Whether the empty skeleton directories in the table are worth fixtures. The
  planner has to classify them as leftovers, so probably yes, as directory
  listings.

## Done when

- `tests/fixtures/` holds every row of the fixtures table, plus a loader that
  presents a job to the planner exactly as intake would see it on the share.
- Each fixture's file count and durations were checked against a fresh listing
  from the pod at capture time. The check exists to catch a truncated capture.
