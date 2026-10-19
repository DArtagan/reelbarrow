# hard-movie-cases: bonus discs, cuts, two films, failed jobs, folds

## Opening prompt

> File the fixtures table's hard movie rows through reelbarrow: Robin Hood
> (cases 2 and 5), The Rescuers (case 6), Field of Dreams (failed jobs) and
> Shrek the Third (case 9). Read `todos/hard-movie-cases.md`, then each case's
> evidence in *The cases* and its rows in *Confidence*, in `docs/design.md`.
> Around the World in 80 Days stays on hold until disc 2 is ripped.

## What each needs

| job | outcome expected by the table | depends on |
|---|---|---|
| Robin Hood, job 35 | two cuts, verified as one film by fingerprint; **labels need a source** (the case photo, or release data naming those exact runtimes) | [editions](editions.md), [review-ui](review-ui.md) |
| Robin Hood, job 36 | a bonus disc; everything goes to Robin Hood's `extras/` | review-ui, since nothing but the case can confirm it's a bonus disc |
| The Rescuers, job 27 | split into two films; raw and extras stay with *The Rescuers (1977)*; `title_71` becomes *The Rescuers Down Under (1990)*, with a pointer `.txt` | identity of the second film by transcript plus runtime, or review |
| Field of Dreams, jobs 30–31 | review: no successful job vouches for the file; keep one of two identical raws | review-ui |
| Shrek the Third, job 28 | fold: ARM's transcode replaces the `.m4v`; the ISO becomes the raw; ARM's MKVs and the old files are leftovers | the fold rules; Plex's watched-state test from [movie-filing](movie-filing.md) |

## Bindings worth restating, because each was a wrong turn once

- The Rescuers' two playlists of near-identical length are **two different
  films**, not two encodes of one (*Correction: the Rescuers "duplicate"*). File
  size compares encodes only when the content is identical.
- A re-authored ISO never matches a pressed disc's pydvdid CRC. For images,
  identity is structural (*Case 9*).

## Done when

Each job's outcome on the share matches its row, verified in Plex and by
listing the folders. Every review in this step went through the review page,
not a database edit.
