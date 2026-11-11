# automatic-filing: the service files what the gate passes

## Opening prompt

> Turn dry run off for reelbarrow's service, so that a plan the gate marks
> automatic is filed without a person. Read `todos/automatic-filing.md`, then
> *The service* (*Plans, their basis, and the inbox*) and *Confidence* in
> `docs/design.md`. Confirm the inbox's gates with Will before the switch.

## Why

The service's half of the fourth step in [README](README.md): from here an
automatic plan goes straight to the executor, and only review and hold plans
wait in the inbox. The review UI is never a confirmation step for what the
gate passed (Will, 2026-11-09, agreeing that automatic plans don't wait for
it). Of the fixtures table's automatic rows, *Monte Carlo or Bust!* (job 34)
was filed by [first-filing](first-filing.md); this files the other two.

## Scope

- **The basis check.** The [executor](executor.md) compares a plan's basis
  with the share immediately before its first operation, and when anything
  differs executes nothing and reports `basis_changed`. What remains is the
  service's half: such a report replans the manifest into the inbox.
- **Every film filed is tagged**: the [embedded-tags](embedded-tags.md) spec's
  `tag` operation is in every automatic plan.
- **Automatic plans go to the executor** as the scan makes them. Review and
  hold plans stay in the inbox.
- **Notify**: Pushover "filed", once [review-ui](review-ui.md) exists to link
  to; until then the web UI's inbox is the record.

## The switch, in the deployment repository

First, confirm in the inbox that only *The Great Race* and *The Polar
Express* are automatic, and every other plan review or hold. Then set `REELBARROW_DRY_RUN` to `"false"` and drop `readOnly` from the
video mount, in one commit.

## Done when

Measured on the share and in Plex:

- Each of the two is visible in Plex without a manual scan.
- Each `raw/` holds the right disc, with `disc.json`.
- `completed/movies/` holds nothing for those jobs, and *The Polar Express*'
  0.4 GB partial raw, `raw/The-Polar-Express`, is gone.
- The ledger's record of each matches the share.
- A plan whose basis was changed between planning and execution, in a test,
  was replanned and not executed.
