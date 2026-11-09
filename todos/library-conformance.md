# library-conformance: the existing library, brought to today's conventions

## Opening prompt

> Run reelbarrow over what is already in the library, most of it filed by hand
> years ago, and bring each entry to the conventions of *Target layout*. Read
> `todos/library-conformance.md`, then *The library's conventions*, *Case 9*,
> *Target layout* and *Any order* in `docs/design.md`. Nothing here has been
> designed beyond this spec's outline; settle the open questions with Will
> before building.

## Why

Proposed by Will on PR #15 (2026-11-09): *"it might be useful to run reelbarrow
on the existing library, ensuring that previously filed entries in the
library, often done manually many years ago, are compliant with our present
best-practice conventions."* It also makes *Any order* cheaper: an entry with a
`disc.json` compares on everything, while one without compares only on what can
be measured from its files.

## Scope

- **A source with no manifest.** Intake builds the record from a scan of the
  entry, as *The manifest* allows for a folder with no producer. Each library
  entry is one unit of work.
- **Plans of conformance only**: the folder renamed to carry `{tmdb-N}`, the
  flat `raw/` split into `raw/<LABEL> [<identity>]/` with `disc.json` where the
  disc's identity can be measured, sidecars and ignore markers written, names
  folded to Latin-1. No media is replaced or deleted here. A better copy
  arriving is *Case 9*'s fold, through an ordinary manifest.
- **The same gate.** A plan files automatically only when its identity meets
  the bar in *Confidence*; anything else is review. A misfiled entry is a bug.

## Open questions

- **Where an entry's identity comes from.** Nothing on the share is evidence of
  identity by its name (`AGENTS.md`), and that includes a hand-made folder name.
  Plex's match (E16: 91 of 96 online-matched) came from the folder's name, so
  it isn't independent of it. The runtime against TMDB's is one signal; what
  is the second?
- **TV entries**, whose layout is *Target layout*'s TV section and whose
  episodes were matched by hand.

## When done

The design's *Target layout* says the 2024 entries keep their flat `raw/` and
are not migrated. That line is replaced by what this spec does.

## Done when

- Every movie entry in the library has a plan, and each automatic one is
  carried out.
- Plex shows each changed entry, with its watched state intact, without a
  manual scan.
- No media file in the library was lost: its count and total size before and
  after, by folder, match apart from sidecars.
