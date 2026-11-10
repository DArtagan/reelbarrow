# plan-inbox: the service plans every manifest into its inbox

## Opening prompt

> Turn reelbarrow's planner into its service: scan the manifests on an
> interval, keep a plan with its basis for each in the inbox, replan when a
> basis changes, and list the inbox read-only in the web UI. Read
> `todos/plan-inbox.md`, then *The service* (*Plans, their basis, and the
> inbox*) in `docs/design.md`. Dry run stays on, so every plan stays in the
> inbox.

## Why

The fourth of the steps in [README](README.md). It is the dry run's "collect
data" half (Will, 2026-10-18: *"Initially we won't want to make actual
changes, just do dry-runs and collect data"*), and it is what
[automatic-filing](automatic-filing.md) and [review-ui](review-ui.md) take
plans from.

## Scope

- **The scan.** The service reads `REELBARROW_MANIFEST_DIR` on an interval and
  plans each manifest whose plan is missing or whose basis no longer matches
  the share. A plan whose basis still matches is not remade. It opens each
  manifest, reads it whole and closes it, never holds one open, and opens
  none more often than the mount's `closetimeo` across every process in the
  pod. Otherwise the share serves it a replaced manifest's old copy
  indefinitely (*Reading the manifests* in `docs/exporter.md`). Whether
  mounting with `closetimeo=0` lifts the second rule is untested; it is a
  deployment change if it does.
- **The inbox**, in SQLite under `REELBARROW_DATA_DIR` beside the
  [executor](executor.md)'s ledger: each plan, its gate, its reasons and its
  basis. A replan replaces the plan it supersedes and keeps the history of
  gates, which is the data the dry run collects.
- **The basis** as the design defines it: the manifest's content, and the
  size and modification time of everything the plan reads and of every library
  path it would change, absent ones included. Analysis results are cached
  against the same size and time, so a rescan with nothing changed reads no
  media.
- **A filed unit's manifest changing** goes to review, not to a fresh plan
  (*The manifest*). The ledger says which units are filed.
- **The web UI** lists the inbox read-only: each manifest, its gate, and its
  plan in plain language.

## Done when

- The deployed pod, in dry run, holds a plan in its inbox for every manifest
  on the share, and their gates match `reelbarrow plan`'s.
- A manifest the exporter rewrites, from a real disc insert, is replanned
  within one interval, and nothing else is.
- A second scan with nothing changed reads no media: measured by the analysis
  cache's hits, not inferred.
- The share is unchanged: the mount is read-only.
