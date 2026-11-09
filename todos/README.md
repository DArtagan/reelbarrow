# Outstanding work

One self-contained spec per step, each meant to be opened cold in its own
session. A file here means the work has not been done. When it is, its permanent
facts go into `docs/`, the spec is deleted, and
[`docs/project_log.md`](../docs/project_log.md) gets a line. See *Project
workflow* in [`AGENTS.md`](../AGENTS.md).

The design every spec builds on is [`docs/design.md`](../docs/design.md). Specs
name the sections they depend on rather than restating them.

## In order

The order is Will's (2026-11-09): the smallest loop that runs end to end first,
then wider. One manifest planned, then filed, then every manifest, then the
service and its inbox, then the review UI, each *"building up from very simple
cases toward progressively harder ones"*. The design's fixtures table (*What is
waiting*) is the acceptance test, each spec taking the rows it names. Dry run
stays on, except for first-filing's one deliberate run, until automatic-filing.
Specs are referred to by name, not number, so finishing one renumbers nothing.

| # | spec | what | needs |
|---|---|---|---|
| 1 | [arm-manifest-export](arm-manifest-export.md) | The exporter that copies ARM's database out as job manifests, run as a sidecar | a real disc, for its last check |
| 2 | [single-manifest-plan](single-manifest-plan.md) | One manifest, *The Hallelujah Trail*, planned and gated, executing nothing; `reelbarrow analyse` and the first fixture | — |
| 3 | [executor](executor.md) | The executor and the ledger: that plan carried out on a test tree, and refused by dry run on the share | single-manifest-plan |
| 4 | [first-filing](first-filing.md) | *The Hallelujah Trail* filed for real by one deliberate run, its preconditions proven, then dry run back on | executor |
| 5 | [manifest-loop](manifest-loop.md) | Every manifest planned, simplest case first, in any order: the whole fixtures table | executor, arm-manifest-export |
| 6 | [plan-inbox](plan-inbox.md) | The service: a plan and its basis per manifest in the inbox, replanned when the basis changes, listed in the web UI | manifest-loop |
| 7 | [automatic-filing](automatic-filing.md) | Dry run off: the service files what the gate passes, the table's other three films | plan-inbox, first-filing |
| 8 | [metrics](metrics.md) | What the service exports, so the cluster can alert on the absence of success | automatic-filing |
| 9 | [review-ui](review-ui.md) | Review page and Pushover for the inbox's review and hold plans: accept, correct, defer | automatic-filing |
| 10 | [editions](editions.md) | Prove the editions naming in Plex, Jellyfin and Kodi before using it | — |
| 11 | [hard-movie-cases](hard-movie-cases.md) | Robin Hood, The Rescuers, Field of Dreams, Shrek the Third | automatic-filing, review-ui, editions |
| 12 | [episode-matching](episode-matching.md) | Inspect harness, reference text, the LLM matcher; Tweety season 1 | automatic-filing, review-ui |
| 13 | [case-photo](case-photo.md) | Photo at insert time, read by a vision model, used as evidence | arm-manifest-export, review-ui, episode-matching |
| 14 | [library-conformance](library-conformance.md) | The existing library, filed by hand years ago, brought to today's conventions | hard-movie-cases, editions |
| 15 | [superseded-sources](superseded-sources.md) | Sources with no manifest that the library already holds better, deleted | hard-movie-cases |

editions needs nothing else and can run whenever there is a free session.

## After these

The `unidentified/` and `raw/` backlog is Will's stated next project; see *The
backlog, roughly* and *Future work* in the design. It gets a spec once
hard-movie-cases has proven the pipeline on hard cases. superseded-sources
clears what of it the library already holds better, so the backlog is what
remains.

## Writing a spec

- **State what was verified and when.** Anything not checked says so.
- **Record why, not just what**, and record decisions Will made verbatim, so they
  are not relitigated.
- **Point at the design rather than restating it.** Two copies drift.
- **End with done-when conditions measured on the share or in Plex**, never
  inferred from the service's own report.
- **Include the opening prompt.**
- **Correct in place.** When a finding is overturned, rewrite the passage and
  note the wrong turn if it could be repeated.
