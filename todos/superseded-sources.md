# superseded-sources: clear out what the library already has better

## Opening prompt

> Plan the deletion of sources on the share that are fully superseded by what
> the library already holds: old, duplicate and incomplete rips under `raw/`
> and `completed/unidentified/` that have no manifest. Read
> `todos/superseded-sources.md`, then *Any order*, *Confidence* and *The
> backlog, roughly* in `docs/design.md`.

## Why

Proposed by Will on PR #15 (2026-11-09): *"we should also support plans that
delete sources that are fully superseded by what's already in the library.
Letting us clean-up old/duplicate/incomplete rips."* A manifest's re-rips
already clean themselves up (*Any order*); this does the same for the sources
that have no manifest. `raw/` holds 2.14 TB, and `LOGICAL_VOLUME_ID` alone has
48 suffixed siblings (*The backlog, roughly*).

## Scope

- **A source with no manifest.** Intake builds the record from a scan of each
  folder under `raw/` and `completed/unidentified/`, as *The manifest* allows.
- **Deletion only, and only of the fully superseded.** A folder is deleted
  when every file in it has its place in the library (work, cut and disc, by
  *Confidence*'s identity rows) filled by a copy equal or better by *Any
  order*'s rules. A folder with one file that isn't superseded is left whole
  for the backlog. Empty folders are leftovers.
- **No identification of new work.** A folder whose content isn't in the
  library is not this spec's: filing it is the backlog's.

## Bindings

- *The Rescuers* "duplicate" was two films (*Correction: the Rescuers
  "duplicate"*): near-identical length is not identity. Supersession needs
  the same identity rows as filing, never size or a name.
- Deleting is acceptable only because the media dataset has snapshots (Will,
  2026-10-04). Check they are current before the first run.

## Done when

- Every folder under `raw/` and `completed/unidentified/` has a plan: delete,
  or left for the backlog with the file that kept it.
- The automatic deletions are carried out, and for a sample of them, the
  superseding copy in the library was opened and played in Plex.
