# single-manifest-plan: one manifest in, one plan out

## Opening prompt

> Finish reelbarrow's single-manifest-plan: job 34's plan, made in the
> deployed pod against the share, matching the one its fixture gives. Read
> `todos/single-manifest-plan.md`, then *The service* (steps 1–6) and
> *Testing* (layer 1) in `docs/design.md`. Everything in this session is
> read-only on the share.

The first of the steps in [README](README.md): one manifest, its inputs
processed and its outputs proposed.

## Why job 34, not job 18

The spec was written for *The Hallelujah Trail*, job 18, whose fixtures-table
row said automatic. Measured on 2026-11-10, its feature runs 155.5 min against
TMDB's 165 (`23194`, the roadshow length the AFI catalogue also gives), −5.7%,
so the ±3% runtime bar sends it to review (E38). Will chose (2026-11-10) to
switch to job 34, *Those Daring Young Men in Their Jaunty Jalopies*, the same
shape: a DVD from before the raw copy's record, film only, one raw MKV. It is
within 2.3% of TMDB's 122 min and files as *Monte Carlo or Bust! (1969)
{tmdb-38792}*, TMDB's English title. The bar stays where the design set it;
job 18 went to [manifest-loop](manifest-loop.md)'s review rows, and the specs
after this one name job 34.

Will also chose (2026-11-10) how intake finds a raw copy no manifest records:
the MKVs written while the job ran, confirmed by content. It is in the
design's step 1.

## Done

On the `single-manifest-plan` branch:

- `reelbarrow analyse <manifest>` and `reelbarrow plan [path]`
  (`reelbarrow.intake`, `.analyse`, `.plan`, `.tmdb`, `.names`).
- Job 34's case, `tests/fixtures/dvd-film-raw-unrecorded/`: its manifest and
  analyse's document, captured in the pod on 2026-11-10, the in-pod and copied
  checksums equal, and a fresh listing there agreeing on file count (one
  each), sizes and durations (7487.913 s each). `tests/test_plan.py` plans it
  automatic, with the row's film and raw, and sends each broken rule to
  review. Its `tmdb.json` is `python -m reelbarrow.tmdb tt0064688`'s
  recording of TMDB's API, 2026-11-10.
- The secret: `REELBARROW_TMDB_TOKEN` in `kubernetes/apps/reelbarrow/secrets.sops.yaml`
  in the deployment repository, taken by the Deployment with `envFrom`, on its
  `video-library-ingest` branch, its value a placeholder until filled in.

## Still to do

- **Deploy**: the token filled in and the secret on `main` in the deployment
  repository; this branch merged and released (see
  [releasing.md](../docs/releasing.md)).
- **The plan in the pod**: `reelbarrow plan --json
  /video/import/automatic-ripping-machine/manifests/manifest-arm-34-178993082181.json`
  in the deployed pod, compared with the fixture's plan. Only the basis's
  library paths can differ, and only if the library has changed.

## Done when

- A layer-1 test plans job 34 from its fixture and asserts its row of the
  fixtures table: automatic, the film and its raw where the row puts them.
  *Met.*
- The fixture's file count and durations matched a fresh listing from the pod
  when it was captured. *Met.*
- `reelbarrow plan` in the deployed pod, against the share, gives the same plan
  as the fixture does.
- The share is unchanged: the mount is read-only.
