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

- **ARM manifests for jobs 1–41.** These are exported once from ARM's database,
  by the export mode of [arm-manifest-hook](arm-manifest-hook.md), into
  `import/automatic-ripping-machine/manifests/`. If they are not there yet, that
  step comes first.
- **The share, read through the reelbarrow pod.** Do not stream media through
  `kubectl exec`: it ran at 17.6 MB/s (E25) and truncated two fingerprints
  (E30). Run the analysis inside the pod, which mounts the share directly, and
  copy out only the results, comparing a checksum taken in the pod with one
  taken after the copy. E30 copied four fingerprints out that way, verified.

## What to capture, per job

ffprobe JSON for every file in its completed and transcode directories and its
raw candidates; video MD5s; fingerprints; Blu-ray hashes; what each raw title
plays (*Title identity* 4), as a DVD image's `lsdvd -c -d -v -Oy` output and a
Blu-ray's playlists read by `bluray_playlists` and its clips' entry points by
`bluray_clips`, as JSON, which is all a decision needs of them; the manifest; and the raw folder's `arm-job.json` where
it has one. Store them under `tests/fixtures/<job>/` in a layout the planner can
load as if it were the share.

The stamps frozen are in `tests/fixtures/stamps/`, every one on the share as
it stood on 2026-10-29: those ARM wrote (jobs 76–80 and 82–87, job 87 being
the *Robin Hood* bonus DVD's re-rip, the first movie disc with `duplicates`)
and those the deployment backfilled (jobs 7, 8, 23, 25 and 27, among them
*The Rescuers* job 27 of the fixtures table), with the contract test that
holds them. A job's own fixture copies its stamp from there rather than
freezing a second one.

A `reelbarrow analyse <path> --out <dir>` command that does this in the pod is
probably the right shape, and the planner's own intake will want it anyway.

## Decisions for this session

- **What a public repository may hold.** ffprobe JSON and hashes are metadata.
  Fingerprints are settled: committed, for the reason under *Testing*, layer 1,
  in the design, and `tests/fixtures/fingerprints/` already holds four from
  jobs 27 and 35. Whisper transcripts of copyrighted programmes are
  text excerpts. Settle whether they are committed whole, trimmed, or kept out
  of git and fetched for evaluations only, and record the reason here.
- Whether the empty skeleton directories in the table are worth fixtures. The
  planner has to classify them as leftovers, so probably yes, as directory
  listings.

## Done when

- `tests/fixtures/` holds every row of the fixtures table, plus a loader that
  presents a job to the planner exactly as intake would see it on the share.
- Each fixture's file count and durations were checked against a fresh listing
  from the pod at capture time. The check exists to catch a truncated capture.
