# release-pipeline: the first release, end to end

## Opening prompt

> Take reelbarrow from its scaffold to a pod running a released image in dry-run
> mode. Read `todos/release-pipeline.md` and `docs/releasing.md`. Nothing here
> has run yet: the workflows, the release-please config and the vulcanus manifests
> were written on 2026-10-18 and checked only locally.

## Where things stand (2026-10-18)

Done and verified:

- CI passes on `main`, `devenv test` on the runner included.
- Release PR #1 bumped `pyproject.toml`, `uv.lock` and the manifest, and wrote
  `CHANGELOG.md`. Merging it tagged `reelbarrow-v0.1.0`, and `publish` pushed
  `ghcr.io/dartagan/reelbarrow:0.1.0` (plus `latest`, which `metadata-action`
  adds by default; the semver policy ignores it). The image pulls anonymously,
  and its revision label equals the tag's commit.
- vulcanus-proxmox deploys it (`video-library-ingest` branch, merged to `main`).
  Flux's `ImagePolicy` resolves `0.1.0`, and the pod is Ready. In-cluster,
  `/healthz` reports `dry_run: true`, and `touch /video/…` fails with
  `Read-only file system`. `https://reelbarrow.immortalkeep.com/` serves the
  version from the LAN.

Remaining: the last done-when below. Release PR #2 (`0.1.1`, a docs change)
is open; merging it is the test. For the `python` release type, `docs:` commits
are releasable, so spec updates here use `chore(todos):`.

## Done when

- The pod is Ready, and `/healthz` reports `dry_run: true` from inside the
  cluster. `https://reelbarrow.immortalkeep.com/` answers from the LAN, the
  vantage point the internal ingress serves, and shows the version.
- `kubectl exec` shows the share mounted read-only: a `touch` under `/video`
  fails with `EROFS`. That is the check the dry-run safety rests on; if it
  succeeds, the mount is wrong.
- A later release, `0.1.1`, reaches the pod with no hand edit in vulcanus:
  Flux Bot commits the tag and the pod rolls.
