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

- **ARM manifests for jobs 1–41.** These are exported once from ARM's database by
  the deployment half into `import/automatic-ripping-machine/manifests/`. If
  they are not there yet, that step comes first, in the deployment repository.
- **The share, read through the reelbarrow pod.** Do not use `kubectl exec`
  streaming: it ran at 17.6 MB/s (E25) and truncated a fingerprint. Run the
  analysis inside the pod, which mounts the share directly, and copy out only
  the results.

## What to capture, per job

ffprobe JSON for every file in its completed and transcode directories and its
raw candidates; video MD5s; fingerprints; Blu-ray hashes; the manifest. Store
them under `tests/fixtures/<job>/` in a layout the planner can load as if it
were the share.

A `reelbarrow analyse <path> --out <dir>` command that does this in the pod is
probably the right shape, and the planner's own intake will want it anyway.

## Decisions for this session

- **What a public repository may hold.** ffprobe JSON and hashes are metadata.
  Fingerprints are derived and cannot be reversed into audio (confirm that in
  [analysis](analysis.md)). Whisper transcripts of copyrighted programmes are
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
