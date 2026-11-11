# embedded-tags: every filed video carries its own identity

## Opening prompt

> Make each video reelbarrow files carry its identity inside the file, as
> Matroska tags, so a file copied out of its folder still says what it is.
> Tag at filing, through the executor's `Writer`, so that *Monte Carlo or
> Bust!* is tagged when first-filing files it. Read `todos/embedded-tags.md`, then
> *Sidecars and embedded metadata* and *Target layout* in `docs/design.md`,
> and *Rules that protect the library* in `AGENTS.md`. Measure mkvpropedit on
> a copy before it touches the library.

## Why

Will asked (2026-11-11), reviewing the executor: *"Hypothetically, for a movie
that's been successfully filed to the library, if in time the manifest is
lost - is there any loss to the integrity of the library's data archive? To
what extent can the library stand-alone?"*

The library stands alone, with one gap. The film's identity is in its folder's
name (`{tmdb-N}`), its `movie.nfo` and `disc.json`, and in none of them once
the file leaves the folder. The design's sidecar table already lists *"inside
each MKV: title and ID tags"*, so it *"travels with the file through any
rename"*. The executor's spec scoped sidecars to the NFO and artwork, so
nothing writes the tags yet. Will: *"Yes please, add that to the specs."*

It comes before [first-filing](first-filing.md) (Will, 2026-11-11, agreeing
to move it there from after), so the first film filed is tagged as it is
filed and nothing reelbarrow files ever needs tagging afterwards. The
in-place edit is then proven in first-filing's deliberate, watched run, not
met for the first time under [automatic-filing](automatic-filing.md).
Tagging what was filed before reelbarrow, the 2024 entries, is
[library-conformance](library-conformance.md)'s.

## Verified, 2026-11-11

- **The tags.** Matroska's tagging specification
  (<https://www.matroska.org/technical/tagging.html>) defines `IMDB`, *"“tt”
  followed by at least 7 digits"*, and `TMDB`, which *"MUST be prefixed with
  either “movie/” or “tv/”"*, so job 34's is `movie/38792`. Beside them sit
  `TITLE` and `DATE_RELEASED`, as global tags at target type 50, `MOVIE`, and
  the segment's own title, which most players show.
- **The tool.** mkvpropedit *"modif[ies] properties of existing Matroska files
  without a complete remux"* (its manual), taking tags as the same XML
  mkvmerge reads (`--tags global:<file>`) and the title as `--edit info --set
  title=…`. MKVToolNix is in neither the image (`Dockerfile`'s `apt-get`
  installs ffmpeg, chromaprint's tools and lsdvd) nor devenv.

**Not verified:**
- How much of a file mkvpropedit rewrites when the new tags don't fit the
  space already there.
- What an interrupted run leaves behind, on CIFS or anywhere.
- Whether ARM's transcodes already carry the track flags and languages the
  design's table also lists.

## Scope

- **Measure first, on a copy.** Tag a copy of a transcode outside the library
  and compare it with the original. Each stream's hash
  (`ffmpeg -map 0 -c copy -f streamhash`) must be identical; the size change
  and the time taken show how much was rewritten. Then interrupt a run part
  way and see whether the file still plays and still hashes the same.
- **A `tag` operation in the plan**, with the tags as its content, carried
  out by the `Writer`: the one place that changes the video root, refused in
  dry run like every other change.
  - **Where it goes in the plan's order is to decide from the measurement.**
    Tagging the transcode in `import/` before anything moves means a failed
    tag stops the filing with nothing moved. Tagging it in the library means
    the tagged file is the one Plex already has.
  - **Its outcome checks the result**: ffprobe reads the tags back, and the
    duration and chapters are unchanged.
- **What each file gets.**
  - A feature: `TITLE` (TMDB's own title, unfolded, since tags are UTF-8
    where names are ASCII), `DATE_RELEASED`, `IMDB` and `TMDB`, and the
    segment title.
  - An extra: as [extras](extras.md) settles it (Will, 2026-11-11). Its
    film's ids always; with a TheDiscDB match its name as `TITLE` and its
    kind as `CONTENT_TYPE`; without one, a `TITLE` made only of what is known.
    This spec makes the operation able to write either.
- **Raw copies aren't tagged** (Will, 2026-11-11: *"Raw copies: leave
  untagged"*). They're the disc's own bytes, kept so the disc can be played
  and transcoded again, and compared byte for byte across rips (E20).
  `disc.json` identifies them.
- **Tags already in the file are kept.** `--tags global:<file>` replaces a
  file's global tags with the file's (mkvpropedit's manual), so read what
  HandBrake and ARM wrote first and write the union. A tag reelbarrow sets
  wins over one already there.
- **Track flags and chapter names**, the rest of the design's row. Measure
  what ARM's transcodes carry first, and plan a change only where one is
  wrong; chapter names have no source yet.
- **The write guard.** mkvpropedit is a subprocess, whose writes neither
  half of the guard sees (`tests/test_write_guard.py`). Extend the static
  scan:
  - only `reelbarrow/executor.py` runs a tool that writes;
  - `analysis/tools.py` runs only tools that read (ffprobe, fpcalc, lsdvd);
  - a test fails when a module is made to run mkvpropedit.
- **MKVToolNix** goes in the image and in devenv, together; *devenv.nix*
  says a version difference between them is the usual reason a test passes
  locally and fails in the image.

## Done when

- The measurement on a copy is recorded here: each stream's hash equal
  before and after, how much of the file was rewritten, and what an
  interrupted run left.
- `reelbarrow plan` on job 34's manifest, in the deployed pod, shows the
  `tag` operation with job 34's tags. The tags reaching the library, and Plex
  keeping its match and watched state, are [first-filing](first-filing.md)'s
  to measure.
- A test files a plan on a share of real MKVs, made by ffmpeg as
  `tests/test_cli.py`'s are, and its film comes out tagged; in dry run the tag
  operation is refused and the file is unchanged. (`cases.Case.build`'s files
  are sparse placeholders, with nothing for mkvpropedit to edit.)
- The write guard fails when a module other than the executor is made to
  run mkvpropedit.
