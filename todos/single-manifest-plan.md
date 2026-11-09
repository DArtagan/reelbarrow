# single-manifest-plan: one manifest in, one plan out

## Opening prompt

> Build the thinnest pass through reelbarrow's pipeline: intake, analyse,
> classify, identify, plan and gate for one manifest, *The Hallelujah Trail*
> job 18, ending in a plan that executes nothing. Read
> `todos/single-manifest-plan.md`, then *The service* (steps 1–6 and *Plans,
> their basis, and the inbox*), *Confidence*, *Target layout* and *Testing*
> (layer 1) in `docs/design.md`. Everything in this session is read-only on
> the share.

## Why this shape (decided 2026-11-09)

The planner was one spec, `dry-run-planner`, covering every case in the
fixtures table before anything was filed, with the executor after it. Will
proposed building the smallest loop that runs end to end first and widening
it: one manifest planned, then filed, then every manifest, then the service and
its inbox, then the review UI, *"building up from very simple cases toward
progressively harder ones"*. This spec is the first of those steps. The order
is in [README](README.md).

Each case's fixture is captured with the rule that reads it, not ahead of it
(Will agreed, 2026-11-09: *"I agree."*). A capture made before its rules has
to guess at what they need and at the loader's shape. The manifest's fields
were chosen the same way, each traced to a rule that reads it; Will,
2026-11-08: *"An interface that includes everything is both fragile and
wasteful."*

## Why job 18

Its row in the fixtures table is automatic: one film, filed as *The Hallelujah
Trail (1965) {tmdb-…}*, its raw `raw/The-Hallelujah-Trail/B1_t00.mkv` beside
it. Its manifest is frozen already in `tests/fixtures/manifests/`. The empty
folders of its failed jobs 15–17 are leftovers, but they belong to those jobs'
manifests, which [manifest-loop](manifest-loop.md) plans.

## Scope

Steps 1–6 for this one case, each built only as far as job 18 needs it, and
each in the form the harder cases will extend rather than replace.

- **`reelbarrow analyse <path> --out <dir>`** comes first. It runs the
  analysis layer over a job's folders in the pod and writes what it measured.
  Its output is the fixtures' form, so the planner reads the same thing from a
  fixture as from the share.
- **Intake** reads a manifest and finds the job's completed and raw folders by
  the paths it records (*The manifest*), checking they are there, never by
  matching names.
- **Classify** as far as one feature and its raw.
- **Identify**: ARM's IMDb ID → TMDB, checked against the feature's runtime
  (±3% to start).
- **Plan**: every operation with its reason, in the layout of *Target layout*:
  renames, the sidecars to write (`movie.nfo`, artwork, `raw/…/disc.json`,
  the ignore markers), and leftover deletions. The plan says what each sidecar
  is; [executor](executor.md) writes it.
- **Gate**: automatic, review or hold, per *Confidence*. A plan is all or
  nothing.
- **`reelbarrow plan <manifest>`** prints the plan and its gate. It records
  nothing; the inbox is [plan-inbox](plan-inbox.md).

## Fixtures, case by case

How every case's fixture is captured, here and in the specs after this one.
When this spec is done, this section moves into *Testing*, layer 1, in the
design.

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
- **No Whisper transcripts.** Whether they are committed is settled in
  [episode-matching](episode-matching.md), the first spec that reads them.

## Bindings from the design that are easy to miss

- Library names come from TMDB and must be folded to Latin-1 the way ARM's
  title hook does in the deployment, until the filename-charset migration
  lands. A name the share would reject with `EIO` is a planning error to catch
  here, not at filing time.
- A movie's feature arrives as `title_N.mkv` above `extras/` since the
  deployment stopped ARM renaming it, and as `<Title (Year)>.mkv` before. Intake
  takes neither name, nor the placement, as the identification.
- The thresholds are starting points, and the evaluation sets them.

## Secrets

A TMDB API key (a free personal key) is the first secret the service needs. Add
it to reelbarrow's encrypted secret in the deployment repository, read it from
the environment, and keep it out of logs.

## Done when

- A layer-1 test plans job 18 from its fixture and asserts its row of the
  fixtures table: automatic, the film and its raw where the row puts them.
- The fixture's file count and durations matched a fresh listing from the pod
  when it was captured.
- `reelbarrow plan` in the deployed pod, against the share, gives the same plan
  as the fixture does.
- The share is unchanged: the mount is read-only.
