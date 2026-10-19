# metrics: let the cluster notice when filing stops

## Opening prompt

> Give reelbarrow the Prometheus metrics the cluster needs to alert on the
> absence of success. Read `todos/metrics.md`. The alert rules live in the
> deployment repository; this spec is the service half.

## The alerts they serve

From the design, in the spirit of "alert on the absence of recent success",
the deployment's rule for every workload:

- A successful ARM job neither filed nor awaiting review after 24 h.
- A review untouched for 7 days.
- The service's own liveness.

## Scope

A `/metrics` endpoint, with enough to express those three without guessing. For
example, per-state job counts, the oldest job in each state as a timestamp, and
the last successful scan and the last filing as timestamps. Timestamps rather
than ages, so a rule's `time() - x` is exact. Check how the deployment's
existing rules measure the same thing for scheduled jobs and backups, and match
them.

The deployment half: a `ServiceMonitor` or `PodMonitor`, and the alert rules.

## Done when

- Each rule's expression returns data in Prometheus, queried rather than
  inferred: a metric name can exist and still have no series.
- Each rule was made to fire once, by holding a job in the state it watches, and
  then to clear.
