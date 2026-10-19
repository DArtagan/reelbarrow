# Releasing and deploying

A release is a deliberate act: merging a commit to `main` does not deploy it.

## How a version is made

1. Commits on `main` follow [Conventional Commits](https://www.conventionalcommits.org/).
   The `convco` commit-msg hook refuses any that do not, because release-please
   reads nothing else.
2. On every push to `main`, release-please updates a standing pull request,
   `chore(main): release X.Y.Z`. It bumps the version in `pyproject.toml` and
   `uv.lock` and writes `CHANGELOG.md` from the commits since the last release.
3. Merging that pull request tags `reelbarrow-vX.Y.Z` and creates a GitHub release. The
   `publish` job then builds the image **from the tag** and pushes
   `ghcr.io/dartagan/reelbarrow:X.Y.Z`.

Below 1.0, a breaking change bumps the minor version rather than the major, and
so do `feat` commits; `fix` bumps the patch.

Release PRs are opened by `github-actions`, and GitHub holds CI on them at
*action required* until someone approves the run from the PR. Approving is
optional: they change only versions and the changelog, and CI runs on `main`
once one is merged. Opening them needs the repository setting *Allow GitHub
Actions to create and approve pull requests*.

## How it reaches the cluster

vulcanus-proxmox deploys reelbarrow from `kubernetes/apps/reelbarrow/`. Flux
polls GHCR, and an `ImagePolicy` with the semver range `>=0.1.0 <1.0.0` selects
the newest release. Flux Bot then commits the new tag into that directory's
`deployment.yaml` on vulcanus-proxmox's `main`. Crossing to 1.0 is a deliberate
edit of that range.

Dry run or live is a property of the deployment, not of a release. Turning
filing on means setting `REELBARROW_DRY_RUN` to `"false"` **and** making the
share mount writable, together, in vulcanus-proxmox.

## Checking a release

The tag, the image and the source should all name the same commit:

```bash
git rev-parse 'reelbarrow-vX.Y.Z^{commit}'
skopeo inspect docker://ghcr.io/dartagan/reelbarrow:X.Y.Z \
  | jq -r '.Labels["org.opencontainers.image.revision"]'
```

The running pod reports its version on `/` and the mode it is in on `/healthz`.
