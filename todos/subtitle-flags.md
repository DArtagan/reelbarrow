# subtitle-flags: a full subtitle track is neither forced nor default

## Opening prompt

> Correct the subtitle flags ARM's transcodes carry, so a film doesn't play
> with subtitles always on, and stop ARM making them wrong. Read
> `todos/subtitle-flags.md`, then *Sidecars and embedded metadata* in
> `docs/design.md`, the `tag` operation and `Writer.tag` that
> [embedded-tags](embedded-tags.md) added, and *Rules that protect the
> library* in `AGENTS.md`. Job 34 is filed by
> [first-filing](first-filing.md) after this, so its flags are right as it
> is filed.

## Why

Measuring what ARM's transcodes carry, for embedded-tags (2026-11-11), found
the full English subtitle track flagged both **default** and **forced** on
every DVD transcode ARM has made. A forced track is meant for the lines a
viewer needs whatever they chose, such as foreign dialogue, so a player that
obeys the flag shows the whole film's subtitles. Will chose a separate spec
for it, and a fix to ARM's preset as well (*"Separate spec; fix ARM's preset
too"*), and ordered it before job 34 is filed: *"Order it so we'll implement
that spec before the first filing of job 34."*

## Verified, 2026-11-11 (E42)

ffprobe in the reelbarrow pod over every MKV in ARM's `completed/`, and
event counts (`-count_packets`) for four films:

| film | track flagged default and forced | events | beside it |
|---|---|---|---|
| job 34, *Monte Carlo or Bust!* | SubRip, English, closed captions | 1,790 | none |
| *Pale Rider* | DVD subpictures, English | 876 | SubRip English 1,322; French 866; Spanish 877 |
| *Field of Dreams* | DVD subpictures, English | 1,703 | Spanish 1,165 |
| *Shrek the Third* | DVD subpictures, English | 1,092 | a forced, non-default English track of 1 event; SubRip English 1,545 |

The same holds, from the flags alone, for every other DVD transcode there:
*An American Tail: Fievel Goes West*, *Around the World in 80 Days*, *Duel*,
*Dust to Glory*, *Le Mans*, *Mad Max*, *Memphis Belle*, *Robin Hood* (2010)
and those of their extras that carry subtitles. The Blu-ray transcodes' tracks (*Downton Abbey*,
*Everything Everywhere All at Once*) are neither. Shrek's one-event track is
what a foreign-audio scan should leave: forced, not default, and short.

ARM's HandBrake preset, `vulcanus-handbrake-preset` in the deployment's ARM
config map, sets `SubtitleAddForeignAudioSearch: true`,
`SubtitleTrackSelectionBehavior: "all"`, `SubtitleBurnBehavior: "none"` and
`SubtitleLanguageList: ["eng", "any"]`.

**Not verified:**
- Why HandBrake flags the full track. The foreign-audio search is the
  likeliest cause; nothing has tested it.
- What Plex, Jellyfin and Kodi each do with a default, forced track, and so
  how each film plays today.
- Job 34's captions are SubRip, which HandBrake can't scan for forced
  subtitles, so how it chose them is unknown too.

## Scope

- **The rule**, as a check the planner makes from the analysis: a subtitle
  track is a full one, not a forced-only one, when its events run through
  the film. Count each subtitle track's events (it reads the whole file,
  which the analysis does already for fingerprints) and settle the measure,
  events per minute or against the same language's other tracks, on the
  four films above. A full track flagged forced, or default, is wrong; a
  short forced track is right and is left alone.
- **The change**, through `Writer` and mkvpropedit as the tags are
  (`--edit track:sN --set flag-forced=0 --set flag-default=0`), in the same
  operation or one beside it, first in the plan, checked by reading the
  flags back. Show Will an example before building it.
- **ARM's preset**, in the deployment repository: what to change so new
  transcodes come out right, tested on a disc before it is relied on. That
  repository's own spec carries the change; this one says what it is.
- **The library's own**, filed by hand before reelbarrow, are
  [library-conformance](library-conformance.md)'s.

## Done when

- `reelbarrow plan` on job 34's manifest, in the deployed pod, plans its
  caption track neither forced nor default, and leaves every other track as
  it is. That the file reaches the library so is
  [first-filing](first-filing.md)'s to measure.
- A test plans and files a real MKV, made by ffmpeg, holding a full track
  flagged forced and a short forced one, and only the full one's flags change.
- A DVD ripped after the preset change comes out with its full subtitle
  track neither forced nor default, measured with ffprobe on the share.
