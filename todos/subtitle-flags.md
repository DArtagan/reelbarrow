# subtitle-flags: a full subtitle track is not forced

## Opening prompt

> Finish subtitle-flags: measure its done-when conditions now the planner's
> rule and ARM's HandBrake argument are built. Read
> `todos/subtitle-flags.md`, then *Subtitle flags* and *Sidecars and
> embedded metadata* in `docs/design.md`, and *Rules that protect the
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

## Verified

**2026-11-11 (E42):** ffprobe in the reelbarrow pod over every MKV in ARM's
`completed/`, and event counts (`-count_packets`) for four films:

| film | track flagged default and forced | events | beside it |
|---|---|---|---|
| job 34, *Monte Carlo or Bust!* | SubRip, English, closed captions | 1,790 | none |
| *Pale Rider* | DVD subpictures, English | 876 | SubRip English 1,322; French 866; Spanish 877 |
| *Field of Dreams* | DVD subpictures, English | 1,703 | Spanish 1,165 |
| *Shrek the Third* | DVD subpictures, English | 1,092 | a forced, non-default English track of 1 event; SubRip English 1,545 |

The same holds, from the flags alone, for every other DVD transcode there.
The Blu-ray transcodes' tracks (*Downton Abbey*, *Everything Everywhere All
at Once*) are neither.

**2026-11-16 (E44), the cause, and the rates.** Captures in
`captures/subtitle-flags/` of Will's checkout.

- **MakeMKV flags the first subtitle track default**, and nothing forced, on
  every raw MKV of those four films. HandBrake keeps a source track's
  default flag (`libhb/preset.c`, `add_subtitle_for_lang`).
- **HandBrake's Matroska muxer flags every default subtitle forced**
  (`libhb/muxavformat.c`), since `7e6a28f65` (jstebbins, 2015-02-24:
  *"mkv: mark 'default' subtitle tracks with both default and forced flags.
  Makes 'default' do the right thing in plex"*). HandBrake then had no way
  to force a track, and its default was mainly for the foreign-audio
  search's forced-only track; that Plex then showed a forced track and not
  a default one is a reading of the commit message, not verified. Issues
  #4063 (2022) and #4848 (2023) asked for Matroska's meaning;
  PR #8187 removed the coupling, merged 2026-10-20, in no release yet. ARM
  runs HandBrake 1.11.2, which has it.
- **The foreign-audio search isn't the cause.** It scans only picture
  tracks (the reproduction below logs *"Skipping subtitle scan. No suitable
  subtitle tracks."* for a SubRip track like job 34's), and on Shrek it made the
  one-event forced-only track; the full track's default, from MakeMKV, came
  after it in the muxer's loop and took the default flag.
- **Reproduced** with nixpkgs' HandBrake 1.11.2 and ARM's preset on an MKV
  made by ffmpeg whose subtitle track was default: out default and forced;
  with `--subtitle-default=none`, neither. HandBrakeCLI's
  `--subtitle-default=none` clears `Default` on every track in the job's
  `SubtitleList` after the preset selects them; the foreign-audio search's
  track is in `Search`, not that list, and keeps default and forced.
- **Events a minute**, each subtitle event's time read by ffprobe on the four
  transcodes: job 34 14.3, Pale Rider 7.5–11.4 across its four tracks, Field
  of Dreams 11.0 and 16.1, Shrek 10.5–16.7, every one with events in each
  tenth of its film; Shrek's forced-only track 0.01.

**Research, 2026-11-16**, for the measure: HandBrake's own search treats a
track with 10% or fewer of the busiest track's events as forced-only
(handbrake.fr/docs/en/latest/advanced/subtitles.html); a Plex forum rule of
thumb, *"usually less than 100, where full subtitles typically have 1000+"*
(forums.plex.tv/t/940751, July 2026); Sublarr classifies signs and forced
tracks by cues a minute and coverage, acting only when confident
(sublarr.de/docs/user-guide/signs-removal). The same Plex thread reports
its *"Shown with foreign audio"* mode turns on forced subtitles in the
audio's language, and that default is right for a full, non-SDH track.

**Not verified:**
- What Plex, Jellyfin and Kodi each do with a default, forced track, or a
  default one; the Plex forum's report above is the nearest.
- How the foreign-audio search chose for Pale Rider and Field of Dreams:
  ARM's logs aren't kept.

## Decisions (Will, 2026-11-16)

- **Clear forced only; keep default.** Offered both flags cleared, as this
  spec first had it, against forced only, once Matroska's meaning of default
  was laid out; chose *"Forced only, keep default"*: *"This is the most 'set
  it and forget it' option, right? Useful both for: normal films (with no
  subtitles shown), foreign films (with player settings to show english
  subtitles in those situations), and english films with occasional foreign
  audio segments."*
- **One operation, renamed `edit`**: the tags, segment title and flags in
  one mkvpropedit run, so one window in which an interruption can damage
  the file, not two. Nothing had been filed, so the rename cost no
  migration.
- **The measure**: 5 events a minute or more is a full track, 1 or fewer
  forced-only, between goes to review; only a forced track is judged.
  *"Your rate settings look reasonable. Do some research online to validate
  your choices"*, which the research above did.
- **ARM: `--subtitle-default=none` now**, rather than waiting for #8187 to
  reach a release and ARM's image, written into the deployment repository's
  spec. New transcodes then have no default subtitle track, which
  reelbarrow doesn't add; once #8187 reaches ARM, the argument can go and
  MakeMKV's default carries through unforced.

## Built

The rule, the analysis it reads, and the `edit` operation, with *Subtitle
flags* in the design describing them:

- `reelbarrow analyse` counts each subtitle track's events, with its codec,
  language and flags, for a completed folder's videos (`Video.subtitles`);
  a raw copy's aren't counted.
- The planner's `subtitles` check; `Edit.subtitles` holds each full track's
  `forced: false`.
- `Writer.edit` sets them with `--edit track:s<n> --set flag-forced=0` in
  the same mkvpropedit run as the tags, and reads back each flag set and
  every other track's as it was.
- Job 34's fixture carries its caption track as E42 and E44 measured it:
  SubRip, English, default and forced, 1,790 events.

Job 34's plan, as the fixture plans it:

```
  ok   subtitles: s1 eng subrip, 1,790 events, 14.3 a minute: a full track, forced
  ...
  edit         import/.../Those-Daring-Young-Men-in-Their-Jaunty-Jalopies (1969).mkv
               the feature's identity and its subtitles' flags, inside the file
               segment title  Monte Carlo or Bust!
               50 MOVIE
                 TITLE          Monte Carlo or Bust!
                 DATE_RELEASED  1969-04-28
                 IMDB           tt0064688
                 TMDB           movie/38792
               subtitle s1    not forced
                 a full track, forced: 1,790 events, 14.3 a minute
```

**ARM's argument** is in the deployment repository's video-library-ingest
spec: `--subtitle-default=none` appended to `HB_ARGS_DVD` and `HB_ARGS_BD`.
The library's own entries, filed by hand before reelbarrow, are
[library-conformance](library-conformance.md)'s.

## Done when

- `reelbarrow plan` on job 34's manifest, in the deployed pod, plans its
  caption track not forced, its default flag and every other track left as
  they are, from an analysis the pod made. That the file reaches the library
  so is [first-filing](first-filing.md)'s to measure.
- A test plans and files a real MKV, made by ffmpeg, holding a full track
  flagged forced and a short forced one, and only the full one's flags
  change. **Done**: `test_file_live_files_the_film_and_scans_it` in
  `tests/test_cli.py`.
- A DVD ripped after ARM's argument is deployed comes out with no subtitle
  track forced but a forced-only one, measured with ffprobe on the share.
