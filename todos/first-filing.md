# first-filing: one film filed for real

## Opening prompt

> File *The Hallelujah Trail* job 18 into the library for real, with one
> deliberate run of `reelbarrow file`, then put dry run back on. Read
> `todos/first-filing.md`, then step 7 of *The service* and *Target layout* in
> `docs/design.md`. This is the first write to the media library. Prove each
> precondition below before turning dry run off, and confirm each change to the
> cluster or the share with Will first.

## Why one film, by hand

Real filing used to wait for the planner to cover every case. One film filed
by a single deliberate run, with nothing else able to file, proves the write
path on the share and in Plex as early as there is a plan worth filing. The
service doesn't plan anything yet, so turning dry run off for the run can file
nothing else.

## Preconditions, each checked rather than assumed

- **Write permission.** The image runs as uid 1000, and the CIFS mount of
  `video-pv` sets no `uid`, `gid`, `file_mode` or `dir_mode` (its options are just
  `rw`), so what that uid may write is unknown. Test it on a scratch directory
  before anything else, and fix the mount in the deployment if needed.
- **Plex keeps watched state** when a folder is renamed and its file replaced.
  This matters for every re-ripped legacy title (*Case 9*). Test it once on a
  throwaway item.
- **Snapshots are current** on `rpool/storage/media`. Deleting leftovers is
  acceptable only because of them (Will, 2026-10-04).
- **The ledger's backup.** From the first real move, the ledger is the only
  history of what was moved where. The deployment repository's guidance on
  adding a stateful workload has the options. A SQLite database with steady
  writes gets a dump.
- **Plex's token** added to reelbarrow's secret in the deployment repository.
- **Job 18's plan is still automatic** and unchanged from the one
  [executor](executor.md) carried out in dry run.

## The run, in the deployment repository

1. Set `REELBARROW_DRY_RUN` to `"false"` and drop `readOnly` from the video
   mount, in one commit.
2. Run `reelbarrow file` on job 18's manifest in the pod.
3. Put both back, in one commit. Dry run stays on until
   [automatic-filing](automatic-filing.md).

## Done when

Measured on the share and in Plex:

- *The Hallelujah Trail* is visible in Plex without a manual scan.
- Its `raw/` holds the right disc, with `disc.json`.
- `completed/movies/` holds nothing for job 18.
- The ledger's record of it matches the share.
- Dry run is back on, and the mount read-only.
