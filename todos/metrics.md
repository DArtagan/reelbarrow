# metrics: let the cluster notice when filing stops

## Opening prompt

> Give reelbarrow the Prometheus metrics vulcanus-proxmox needs to alert on the
> absence of success. Read `todos/metrics.md`. The alert rules live in
> vulcanus-proxmox; this spec is the service half.

## The alerts they serve

From the design, in the spirit of "alert on the absence of recent success"
(vulcanus-proxmox `docs/README.md`):

- A successful ARM job neither filed nor awaiting review after 24 h.
- A review untouched for 7 days.
- The service's own liveness.

## Scope

A `/metrics` endpoint, with enough to express those three without guessing. For
example, per-state job counts, the oldest job in each state as a timestamp, and
the last successful scan and the last filing as timestamps. Timestamps rather
than ages, so a rule's `time() - x` is exact. Check what vulcanus-proxmox's
existing rules do for the same problem (`CronJobHasNeverSucceeded`, the backup
coverage check) and match them.

The vulcanus half: a `ServiceMonitor` or `PodMonitor`, and the rules in
`kubernetes/infrastructure/prometheus-rules.yaml`.

## Done when

- Each rule's expression returns data in Prometheus, queried rather than
  inferred. vulcanus-proxmox's `CLAUDE.md` says why: names that exist can still
  have no series.
- Each rule was made to fire once, by holding a job in the state it watches, and
  then to clear.
