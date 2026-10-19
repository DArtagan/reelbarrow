# Outstanding work

One self-contained spec per step, each meant to be opened cold in its own
session. A file here means the work has not been done. When it is, its permanent
facts go into `docs/`, the spec is deleted, and
[`docs/project_log.md`](../docs/project_log.md) gets a line. See *Project
workflow* in [`CLAUDE.md`](../CLAUDE.md).

The design every spec builds on is [`docs/design.md`](../docs/design.md). Specs
name the sections they depend on rather than restating them.

## In order

The design's fixtures table (*What is waiting*) is the acceptance test for
steps 1 to 10. Dry run stays on through step 4; step 5 is the first that changes
the share.

| # | spec | what | needs |
|---|---|---|---|
| 1 | [release-pipeline](release-pipeline.md) | First release end to end: tag, image, Flux, pod | deployment manifests |
| 2 | [analysis](analysis.md) | The measuring primitives: ffprobe, video MD5, fingerprints and alignment, Blu-ray hashes | — |
| 3 | [fixtures](fixtures.md) | Frozen fixtures for every job in the fixtures table, captured from the share | 1, 2; ARM manifests exported |
| 4 | [dry-run-planner](dry-run-planner.md) | Intake → analyse → classify → identify films → plan → gate, recorded and shown, executing nothing | 2, 3 |
| 5 | [movie-filing](movie-filing.md) | The executor: the four unambiguous films filed for real, Plex refreshed, leftovers deleted | 4 |
| 6 | [metrics](metrics.md) | What the service exports, so the cluster can alert on the absence of success | 5 |
| 7 | [review-ui](review-ui.md) | Review page and Pushover: accept, correct, defer | 4 |
| 8 | [editions](editions.md) | Prove the editions naming in Plex, Jellyfin and Kodi before using it | — |
| 9 | [hard-movie-cases](hard-movie-cases.md) | Robin Hood, The Rescuers, Field of Dreams, Shrek the Third | 5, 7, 8 |
| 10 | [episode-matching](episode-matching.md) | Inspect harness, reference text, the LLM matcher; Tweety season 1 | 5, 7 |
| 11 | [case-photo](case-photo.md) | Photo at insert time, read by a vision model, used as evidence | 7, 10 |

Step 8 needs nothing else and can run whenever there is a free session.

## After these

The `unidentified/` and `raw/` backlog is Will's stated next project; see *The
backlog, roughly* and *Future work* in the design. It gets a spec once step 9
has proven the pipeline on hard cases.

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
