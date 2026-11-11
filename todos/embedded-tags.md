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

## Measured on a copy, 2026-11-11 (E41, E42)

Job 34's transcode, 1,821,842,964 bytes, copied out of the pod and checked
against the pod's checksum (`b82ce883…`): the first `kubectl exec cat` came
out 3.7 MB short, as E30 warns, and the rest was fetched from the offset.
Measured locally with mkvpropedit 102.0, then again in the built image with
its 92.0.

- **Streams.** Each of the four streams' hash (`-f streamhash`) is identical
  before and after.
- **What is rewritten.** HandBrake writes its tags at the head, directly
  before the first cluster, with no padding after them, and the chapters and
  cues at the tail. mkvpropedit moved the segment information into the
  63-byte void before it, blanked the old tags, and appended the new ones:
  983 bytes changed at the head, 502 appended, nothing between. It took
  0.06 s, in 19 small writes in place, with no temporary file and no fsync.
  Two runs give byte-identical files.
- **Interrupted.** Killed before each of its 19 writes in turn (strace's
  fault injection), the streams survived every time. The metadata didn't:
  some states have no duration, or fail mkvinfo; a second run refuses 7 of
  the 19 (*"corrupted and cannot be modified safely"*); after 2 it reports
  success yet mkvinfo still finds fault, which ffprobe passes over in
  silence; after 10 the file is sound but has lost HandBrake's per-track
  tags, voided before the new ones were written. A remux by mkvmerge
  rebuilds the worst of them, but with every stream's hash changed, so it is
  no exact repair.
- **Track flags.** On every DVD transcode ARM has made, the full English
  subtitle track is both default and forced; job 34's is 1,790 closed
  captions. That is [subtitle-flags](subtitle-flags.md)'s.

**Not verified:** an interruption on CIFS itself. The pod mounts the share
read-only, so the measurement was local; mkvpropedit makes the same calls
either way.

## Decided, 2026-11-11

- **The tag goes first, on the transcode in `import/`, before anything
  moves.** Will chose it, offered against tagging last in the library and
  against keeping a copy of the bytes an edit can change: an edit that fails
  stops the filing with the library untouched, and a damaged transcode stays
  out of Plex's sight, its raw copy still there to transcode again. A filing
  stopped before its record's folder is made writes no record; the report is
  the account.
- **The file is checked before and after**: mkvinfo exits 0, which catches
  the damage ffprobe passes over; ffprobe reads back the segment title and
  every tag; the duration and the chapters' starts are as they were.
- **The tags pass to mkvpropedit in memory**, a `memfd` it opens by
  `/proc/self/fd/<n>`: it can't read them from a pipe, and a temporary file
  is a write the guard would have to allow. Will asked why a file at all.
- **Subtitle flags are a separate spec**, done before first-filing, and ARM's
  preset is fixed too (Will: *"Separate spec; fix ARM's preset too"*, and
  *"Order it so we'll implement that spec before the first filing of job
  34."*).
- **The segment title and `TITLE` both**: the segment title names the file,
  which most players show; `TITLE` at level 50 is the tagging system's
  account of what the content is, beside the ids. For a feature they agree;
  for an extra they can differ.

The example Will agreed (*"Yes, now build it as shown."*), as `reelbarrow
plan` renders job 34's first operation:

```
  tag          import/automatic-ripping-machine/completed/movies/Those-Daring-Young-Men-in-Their-Jaunty-Jalopies (1969)/Those-Daring-Young-Men-in-Their-Jaunty-Jalopies (1969).mkv
               the feature's identity, inside the file
               segment title  Monte Carlo or Bust!
               TITLE          Monte Carlo or Bust!
               DATE_RELEASED  1969-04-28
               IMDB           tt0064688
               TMDB           movie/38792
```

and the file's tags afterwards, by `mkvextract`: HandBrake's four per-track
`DURATION`s untouched, its `ENCODER` kept, and a tag at level 50, `MOVIE`,
holding the four above.

## Scope

- **Measure first, on a copy.** Tag a copy of a transcode outside the library
  and compare it with the original. Each stream's hash
  (`ffmpeg -map 0 -c copy -f streamhash`) must be identical; the size change
  and the time taken show how much was rewritten. Then interrupt a run part
  way and see whether the file still plays and still hashes the same.
- **A `tag` operation in the plan**, with the tags as its content, carried
  out by the `Writer`: the one place that changes the video root, refused in
  dry run like every other change.
  - **It goes first**, on the transcode in `import/` (*Decided*, above).
  - **Its outcome checks the result**: mkvinfo finds no fault, ffprobe
    reads the tags back, and the duration and chapters are unchanged.
  - **The planner gates on Matroska**: a feature that isn't an MKV can't
    carry its tags, so its plan goes to review rather than filing untagged.
- **What each file gets.**
  - A feature: `TITLE` (TMDB's own title, unfolded, since tags are UTF-8
    where names are ASCII), `DATE_RELEASED`, `IMDB` and `TMDB`, and the
    segment title.
  - An extra: as [extras](extras.md) settles it (Will, 2026-11-11). Its
    film's ids always; with a TheDiscDB match its name as `TITLE` and its
    kind as `CONTENT_TYPE`; without one, a `TITLE` made only of what is known.
    This spec makes the operation able to write either.
- **No other tags.** `ORIGINAL_MEDIA_TYPE`, `DATE_DIGITIZED` and a custom
  `_REELBARROW_DISC` linking the file to its disc were offered, with the
  descriptive tags the NFO already holds, and declined (Will, 2026-11-11:
  *"No thanks."*).
- **Raw copies aren't tagged** (Will, 2026-11-11: *"Raw copies: leave
  untagged"*). They're the disc's own bytes, kept so the disc can be played
  and transcoded again, and compared byte for byte across rips (E20).
  `disc.json` identifies them.
- **Tags already in the file are kept.** `--tags global:<file>` replaces a
  file's global tags with the file's (mkvpropedit's manual), so read what
  HandBrake and ARM wrote first and write the union. A tag reelbarrow sets
  wins over one already there.
- **Track flags and chapter names**, the rest of the design's row. ARM's
  transcodes carry each track's language; their subtitle flags are wrong,
  and [subtitle-flags](subtitle-flags.md)'s. Chapter names have no source
  yet.
- **The write guard.** mkvpropedit is a subprocess, whose writes neither
  half of the guard sees (`tests/test_write_guard.py`), so both judge a tool
  by its name:
  - only `reelbarrow/executor.py` runs a tool that writes;
  - `analysis/tools.py` runs only tools that read (ffprobe, fpcalc, lsdvd,
    and ffmpeg, whose command must end in `-`, its stdout);
  - a test fails when a module is made to run mkvpropedit.
- **MKVToolNix** goes in the image and in devenv, together; *devenv.nix*
  says a version difference between them is the usual reason a test passes
  locally and fails in the image. They differ: devenv's is 102.0, Debian
  trixie's 92.0. The tag, guard, executor and CLI tests pass in the built
  image too, and its `Writer.tag` on job 34's copy gives the same tags and
  equal streams.

## Done when

- ~~The measurement on a copy is recorded here~~: done, above.
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
