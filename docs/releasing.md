# Releasing and deploying

A release is a deliberate act: merging a commit to `main` does not deploy it.

## How a version is made

1. Commits on `main` follow [Conventional Commits](https://www.conventionalcommits.org/).
   The `convco` commit-msg hook refuses any that do not, because release-please
   reads nothing else.
2. On every push to `main`, release-please updates a standing pull request,
   `chore(main): release X.Y.Z`. It bumps the version in `pyproject.toml`,
   `uv.lock` and the example `compose.yaml`, and writes `CHANGELOG.md` from the
   commits since the last release.
3. Merging that pull request tags `vX.Y.Z` and creates a GitHub release. The
   `publish` job then builds the image **from the tag** and pushes
   `ghcr.io/dartagan/reelbarrow:X.Y.Z`, and `latest`.

Releases are immutable once published: GitHub refuses to change a release's
tag. That is why 0.1.0 alone is tagged `reelbarrow-v0.1.0`, from before tags
dropped the package name; `v0.1.0` marks the same commit.

Below 1.0, a breaking change bumps the minor version rather than the major, and
so do `feat` commits; `fix` bumps the patch.

Release PRs are opened by `github-actions`, and GitHub holds CI on them at
*action required* until someone approves the run from the PR. Approving is
optional: they change only versions and the changelog, and CI runs on `main`
once one is merged. Opening them needs the repository setting *Allow GitHub
Actions to create and approve pull requests*.

## Merging a pull request

The pull request's title decides how it is merged. GitHub writes the title into
every merge commit, and release-please reads a Conventional Commit anywhere in a
message.

- **A conventional title** (`fix: …`, `feat: …`) means **squash**. The title
  becomes the one commit on `main` and the one line in the changelog; the
  branch's own commits stay in the pull request. It is the usual case, and the
  only one where a `BEGIN_COMMIT_OVERRIDE` block in the pull request's body can
  correct a note after merging.
- **A plain title**, such as the branch name and a summary, means a **merge
  commit**, for when each commit on the branch belongs in the history. Those
  commits write the notes, and the title writes nothing. The lower of two
  stacked pull requests needs this: squashing it gives `main` a copy of its
  commits, which the branch above then conflicts with.

A merge commit under a conventional title puts every change in the changelog
twice. Retitle the pull request whenever the branch changes which kind it is;
only the title at merge time counts.

### Several notes from one squash

A squash gives the changelog one line, its title. A pull request that adds
several things a reader of the release notes would want to see apart lists
them instead, in a block at the end of its body:

```
BEGIN_COMMIT_OVERRIDE
feat(executor): carry out automatic plans through one Writer, which refuses every change while dry run is on
feat(cli): `reelbarrow file` files each automatic plan, and leaves review and hold plans alone
docs(todos): the embedded-tags and extras specs, ahead of first-filing and manifest-loop
END_COMMIT_OVERRIDE
```

- **Each line is one Conventional Commit**, and becomes one changelog entry,
  under its type's heading. The block replaces the title's entry rather than
  adding to it, so the title's own change is listed too if it still belongs.
- **It describes what the pull request leaves, not how it got there.** A branch
  that built something and replaced it before merging lists only what remains;
  merging its commits would put both in the notes.
- **It is read from the merged pull request's body** each time release-please
  runs, so it can be added or corrected after merging, until the release pull
  request is merged.
- **Its entries link to the squash commit**, not to the pull request's number.
- **The marker is only ever the block.** release-please reads everything after
  it in the body as the override, so a description that mentions it in
  passing, even in backticks, becomes an override that doesn't parse, and the
  pull request drops out of the changelog. Write "the commit-override block" in
  prose instead.

release-please itself succeeds when it can't parse a commit, so the release
workflow's `commits-parsed` job reads its log and fails a check on the open
release pull request, *release notes: commits parsed*, before it is merged.
When it does, correct the merged pull request's title or block, and rerun all
of the workflow's jobs (`gh run rerun <run>`), not only the failed one, so
that release-please reads them afresh; the check passes on that run. The check
is not required, so a release pull request can still be merged past it, and a
release merged so loses the entry for good.
- The squash commit's body, which lists the branch's commits as bullets, adds
  nothing to the changelog either way.

Use it where a squash would undersell the pull request. A merge commit is for
history that belongs on `main`, not for a fuller changelog: a branch's commits
record its review, and say what changed along the way.

## How it reaches the cluster

Flux deploys reelbarrow from the deployment repository (see *The deployment
half* in `AGENTS.md`). It polls GHCR, and an `ImagePolicy` with the semver range
`>=0.1.0 <1.0.0` selects the newest release. Flux Bot then commits the new tag
into reelbarrow's `Deployment` there. Crossing to 1.0 is a deliberate edit of
that range.

Dry run or live is a property of the deployment, not of a release. Turning
filing on means setting `REELBARROW_DRY_RUN` to `"false"` **and** making the
share mount writable, together, in the deployment repository.

## Checking a release

The tag, the image and the source should all name the same commit:

```bash
git rev-parse 'vX.Y.Z^{commit}'
skopeo inspect docker://ghcr.io/dartagan/reelbarrow:X.Y.Z \
  | jq -r '.Labels["org.opencontainers.image.revision"]'
```

The running pod reports its version on `/` and the mode it is in on `/healthz`.
