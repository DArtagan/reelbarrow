# case-photo: evidence captured while the disc is in hand

## Opening prompt

> Add the insert-time case photo to reelbarrow: a Pushover link when ARM finds a
> disc, a one-button camera page, and a vision model that turns the photo into
> evidence the gate can use. Read `todos/case-photo.md`, then *The case photo*
> and *Confidence* in `docs/design.md`.

## Why

It captures evidence for cases 2–6 (disc numbers, bonus discs, edition names,
episode lists) at the one moment it is cheap. That answers Will's concern about
*"not losing opportunity to access information (e.g. while the original disc is
in hand)"*. A photo is welcome *"as long as the process is as straight-forward as
possible"* (2026-10-03). It is optional: a job with no photo proceeds on the
other evidence.

## Scope

- Triggered by the "Found disc" manifest, which ARM's hook writes before the rip
  starts. Confirm the vulcanus half writes it at that point.
- A page that is a camera button and nothing else. The photo is stored with the
  job.
- Vision extraction through the same model interface as
  [episode-matching](episode-matching.md): title, year, disc number, edition
  names, and episode lists per disc.
- Feed the extraction into the gate as one signal among others. It is never
  enough to file on alone.

## Done when

- The Inspect evaluation over a dozen cases of films already filed passes.
  Will's brother photographs them, and their answers are known.
- One real disc goes from insert to photo to a plan that cites the photo's
  evidence.
