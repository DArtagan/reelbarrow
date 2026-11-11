# extras: named from TheDiscDB, filed by kind where Plex sees them

## Opening prompt

> Settle how reelbarrow names and files a film's extras: TheDiscDB's name and
> kind where it knows the disc, otherwise `Other/<disc label>_title_<n>.mkv`,
> in the kind folders Plex reads, proven in Plex, Jellyfin and Kodi. Read
> `todos/extras.md`, then *Decisions already made* (the two on extras) and
> *Extras* under *Target layout* in `docs/design.md`.

## Why

Two things came up while reviewing the executor (2026-11-11).

**Plex doesn't see the library's extras.** The 2024 entries keep them in
`extras/`, as the design did for unnamed extras (Will, 2026-10-04). Plex's
list of extras folders has no `extras`. Of the 44 MKVs in the `extras/` of
14 film folders, Plex lists none as an extra or as part of its film. The
section has *Use local assets* on and *Only show trailers* off, so no setting
explains it.

**Will chose how extras are named.** He was offered TheDiscDB, the film's
ids only, an honest generic title, the case photo, a transcript with an LLM,
and the review UI, and chose: *"#3 where possible. When that doesn't work, #2
for the filename and #1 for the embedded-tags. In the future, we might do #4
and maybe even contribute back to TheDiscDB."*
- **The layout**: Plex's kind folders, with `Other/` for an unknown kind.
- **An unmatched extra's file**: *"`disclabel_title_n.mkv`. We'll need to
  check for the case of two discs having the same label (e.g. processing
  something like The Return of the King where there's multiple discs being
  merged together, and they might each have their own extra titles)"*.

It comes before [manifest-loop](manifest-loop.md), which plans *The Great
Race* (one extra) and *The Polar Express* (three), so the layout is settled
before anything files an extra.

## Verified, 2026-11-11

- **Plex** reads `Behind The Scenes`, `Deleted Scenes`, `Featurettes`,
  `Interviews`, `Scenes`, `Shorts`, `Trailers` and `Other`, or a suffix
  (`-featurette`) on a file beside the film
  (<https://support.plex.tv/articles/local-files-for-trailers-and-extras>).
  **Jellyfin** reads the same names, lowercase, plus `extras` and `clips`.
  **Kodi** v21 reads one `Extras` folder, and only with *Ignore video extras
  on scan* turned off. Otherwise it may scan those videos as films
  (<https://kodi.wiki/view/Video_extras>).
- **TheDiscDB** publishes its data under MIT at
  <https://github.com/TheDiscDb/data> (1.6 GB with images; updated the day it
  was read). It holds one JSON file per disc. Heat's 2022 Blu-ray's
  `disc01.json` has:
  - the disc's `Format`, `ContentHash` and `GlobalDiscId`;
  - each title with its `SourceFile` (`00350.mpls`), `Duration` (`2:50:18`),
    `Size`, and `Item` with its `Title` and `Type` (`MainMovie`; `null` for a
    title nobody labelled).

  Its site says a DVD's id is *"calculated from a DVD's control data"*, and its
  fingerprint is *"a Matrix256 hash calculated from the relative path and size
  of every file on the disc"*. It held 6,510 discs.

**Not verified:**
- Whether a DVD's id there is the pydvdid CRC64 ARM records, or anything
  reelbarrow can compute from a raw copy.
- How a DVD's titles are numbered there.
- How much of this collection it covers. E10 found no Tweety.
- Whether Plex shows an extra in `Other/` or `Featurettes/` over the CIFS
  mount.

## Scope

- **Matching a disc in TheDiscDB.**
  - Find which of its identifiers reelbarrow can compute or already holds. For
    a DVD, that's ARM's CRC64, or the image's control data where the raw copy
    is an image. For a Blu-ray, the backup's files, which a path-and-size
    fingerprint covers.
  - Read the data from the repository, pinned to a commit and searched
    locally, or from TheDiscDB's site; decide which.
  - The replies a decision reads become fixtures, trimmed, as TMDB's are.
- **Coverage.** Look up every disc in the fixtures table and the raw backlog,
  and record how many TheDiscDB knows, with their titles named.
- **Naming a title from it.**
  - A title takes TheDiscDB's name and kind only when the disc matches and the
    title agrees in both its number (`disc_title`, or the playlist) and its
    length. Anything less falls back.
  - A fallback is safe, so it never sends a plan to review. A wrong name taken
    from a wrong match is a misfile (*Confidence*).
  - TheDiscDB's types map to Plex's folders, and anything unmapped to `Other`.
- **The fallback name**, `<disc label>_title_<n>.mkv`, with the label folded as
  every library name is (`reelbarrow.names`) and `n` the disc's own number.
  - A Blu-ray's number is its playlist's: settle with Will whether that reads
    as `_title_00011` or otherwise.
  - Two discs with one label, filed into one film, could meet on a name. Find
    whether the share holds such a case, and settle with Will how they're told
    apart. The raw folder's own name, `<label> [dvd-<crc64>]`, already tells
    them apart.
- **Embedded tags** for an extra, through [embedded-tags](embedded-tags.md)'s
  operation: its film's `IMDB` and `TMDB`. With a TheDiscDB match, its name as
  `TITLE` and its kind as `CONTENT_TYPE`. Without one, a `TITLE` made only of
  what is known (the film, and the disc's number for the title) and no
  `CONTENT_TYPE`.
- **The layout, proven in the players** before anything files into it, beside
  [editions](editions.md)'s naming:
  - one extra each in `Other/` and a kind folder shows in Plex as its film's
    extra, of that kind;
  - Jellyfin shows the same;
  - Kodi's behaviour is recorded.
- **disc.json** follows: a filed extra's `transcode` is its path in its kind
  folder.

The 2024 entries' 44 files in `extras/` are
[library-conformance](library-conformance.md)'s to move. Naming from the case
photo, and contributing discs back to TheDiscDB, are *Future work* in the
design.

## Done when

- The fixtures table's discs and the raw backlog have been looked up in
  TheDiscDB, and how many it knows is recorded here.
- In Plex, an extra filed in `Other/` and one in a kind folder each show as
  their film's extra, of that kind, and Jellyfin likewise. Kodi's handling is
  recorded.
- The planner, given recorded TheDiscDB replies, names an extra TheDiscDB
  knows and falls back for one it doesn't, in tests. Two discs sharing a label
  get distinct names.
