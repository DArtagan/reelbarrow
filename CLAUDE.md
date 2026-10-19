# CLAUDE.md

Guidance for coding agents working in this repository.

reelbarrow files automatic-ripping-machine's output into the video library Plex
reads. [`docs/design.md`](docs/design.md) is the design: the cases an ingest must
tell apart, the identity techniques that were measured to work, the confidence
gate, the testing strategy and the target layout. Read the sections a spec names
before changing behaviour; most rules there exist because the obvious approach
was tried on real discs and failed.

## Development environment

[devenv](https://devenv.sh/) provides Python 3.13, uv, ffmpeg, chromaprint, `gh`,
`jq` and `skopeo`. `direnv` loads it on `cd`; otherwise `devenv shell`.

```bash
uv add <package>               # a runtime dependency; --group dev for a test one
pytest                         # the tests
treefmt                        # format the tree
devenv test                    # every hook over every tracked file, as CI runs it
reelbarrow serve               # the web UI on :8000
```

The hooks are the ones `git commit` runs: treefmt, ruff, pytest, and `convco` on
the commit message. Files git does not track are invisible to them; `git add -N`
a new file first.

### Working here as an agent

- **`git diff --no-ext-diff`.** The global git config sends `git diff` through
  difftastic, whose side-by-side output is several times the size.
- **Verify with `devenv test`, not by printing files back.**
- **Filter noisy commands** down to the lines that carry the result.

## Rules that protect the library

- **Dry run is the default, and it must be impossible to bypass by accident.**
  `REELBARROW_DRY_RUN` is true unless set to `false`. Every change to the share,
  whether rename, write or delete, goes through a single executor that checks
  it. No other code opens anything under the video root for writing, and a test
  holds that line from the moment the executor exists.
- **A misfile is a bug, not a tuning problem.** Per the design's *Confidence*
  section, the fix is a new rule plus a regression fixture, never a confirmation
  step.
- **Nothing on the share is evidence of identity by its name.** `title_N` numbering
  and `_<stage>` directory suffixes change between rips of the same disc.
- **Real media never enters the repository.** Tests run on frozen fixtures
  derived from the media: ffprobe JSON, fingerprints, transcripts, manifests.
  The repository is public, so a fixture holds what a decision needs and no more.
  Secrets live in the deployment repository, encrypted, and reach the service
  through the environment.

## Project workflow

Work is specified in [`todos/`](todos/README.md), one self-contained spec per
step, ordered in that README. A spec's filename without `.md` is its **slug**,
which names the branch it is worked on. Work happens on that branch and lands on
`main` through a pull request.

When a spec is done, whatever it leaves permanently true goes into `docs/`, and
the spec is deleted in the same pull request, with a line added to
[`docs/project_log.md`](docs/project_log.md). A retired slug is never reused.

Commits follow [Conventional Commits](https://www.conventionalcommits.org/);
release-please builds versions and the changelog from them. Releasing and
deploying are in [`docs/releasing.md`](docs/releasing.md). A merge to `main`
deploys nothing until the release pull request is merged.

### The deployment half

reelbarrow runs on a Kubernetes cluster deployed by Flux from a separate GitOps
repository, called **the deployment repository** throughout this one. It holds
reelbarrow's manifests and secrets, ARM's manifest hook and the alert rules, and
has its own spec for that half and its own rules for changing it. A spec here
that needs a deployment change says what has to change, not how that repository
is laid out. Where it is checked out is in `CLAUDE.local.md`, which is not
committed.

### Debugging captures

Anything pulled from a running system, such as ffprobe dumps, fingerprints,
transcripts or logs, goes under `captures/<topic>/` at the root of the checkout.
`.gitignore` excludes it. `captures/design/` holds the prototypes and results
from the design sessions; the experiments table in the design names what each
is. Whatever a conclusion rests on beyond the session
belongs in a spec or in `docs/` as quoted figures.

## How it is phrased

Comments and docs describe what is, in present tense, and carry the reason where
a reader could otherwise reintroduce a bug. Dates and history belong in specs and
commit messages. A fact lives in one place.
