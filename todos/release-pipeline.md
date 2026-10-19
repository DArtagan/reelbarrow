# release-pipeline: the first release, end to end

## Opening prompt

> Take reelbarrow from its scaffold to a pod running a released image in dry-run
> mode. Read `todos/release-pipeline.md` and `docs/releasing.md`. Nothing here
> has run yet: the workflows, the release-please config and the vulcanus manifests
> were written on 2026-10-18 and checked only locally.

## Where things stand (2026-10-18)

Written and checked locally:

- `.github/workflows/ci.yaml` runs `devenv test` and builds the image without
  pushing. `devenv test` passes on the workstation.
- `.github/workflows/release.yaml` runs release-please, then builds and pushes
  `ghcr.io/dartagan/reelbarrow:X.Y.Z` from the release tag.
- The image builds locally with Podman. As uid 1000, `/healthz` returns
  `{"status":"ok","dry_run":true}`, and `ffprobe` 7.1.5 and `fpcalc` 1.5.1 are
  present.
- In vulcanus-proxmox, `kubernetes/apps/reelbarrow/` holds the deployment on the
  `video-library-ingest` branch. It is **not yet listed** in
  `kubernetes/apps/kustomization.yaml`, because the image it names does not exist
  yet, and listing it would leave a pod in `ImagePullBackOff`.

Never exercised:

- **release-please's update of `uv.lock`.** `release-please-config.json` bumps
  the root package's version there through a `toml` extra-file with the
  jsonpath `$.package[?(@.name.value=='reelbarrow')].version`. That expression
  was written from memory of others' configs, not tested. If it matches nothing,
  the release PR bumps `pyproject.toml` alone, and `uv sync --locked` then fails
  in both CI and the image build.
- `devenv test` on a GitHub runner, using `nix profile install nixpkgs#devenv`.
  The runner's devenv may not be the 2.4.0 the lock was made with.
- Whether the GHCR package comes out public. trello-randomizer's did, from the
  same kind of workflow, and its deployment pulls with no credentials.

## Steps

1. Push `main` and watch CI. Fix whatever the runner disagrees with.
2. Confirm release-please opened `chore(main): release 0.1.0`, and **read its
   diff before merging**: `pyproject.toml`, `uv.lock` and `CHANGELOG.md` must all
   say `0.1.0`. If `uv.lock` does not, fix the jsonpath; release-please's
   `toml` updater docs and its tests are the reference.
3. Merge it. Check the `publish` job built from the tag, using the commands in
   *Checking a release* in `docs/releasing.md`. Make the GHCR package public if it
   is not.
4. In vulcanus-proxmox, following its `CLAUDE.md`: add `reelbarrow` to
   `kubernetes/apps/kustomization.yaml` on the `video-library-ingest` branch,
   set the image tag to `0.1.0`, and deploy.
5. Check that Flux's `ImagePolicy` `apps:reelbarrow` resolves `0.1.0`
   (`flux get image policy -n apps reelbarrow`).

## Done when

- The pod is Ready, and `/healthz` reports `dry_run: true` from inside the
  cluster. `https://reelbarrow.immortalkeep.com/` answers from the LAN, the
  vantage point the internal ingress serves, and shows the version.
- `kubectl exec` shows the share mounted read-only: a `touch` under `/video`
  fails with `EROFS`. That is the check the dry-run safety rests on; if it
  succeeds, the mount is wrong.
- A trivial `fix:` commit, merged and released as `0.1.1`, reaches the pod with no
  hand edit in vulcanus: Flux Bot commits the tag and the pod rolls.
