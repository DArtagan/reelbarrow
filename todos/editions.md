# editions: prove the naming before using it

## Opening prompt

> Test the candidate editions naming in `docs/design.md` (*Editions*) against
> Plex, a throwaway Jellyfin, and Kodi, then adopt it or replace it. Read
> `todos/editions.md`. No code in reelbarrow depends on the answer yet.

## Why

*"We need a way to verify before we go forward. And in the case of editions, we
still need to file both to the file-system library in a manner that is
future-portable."* (Will, 2026-10-04). Plex and Jellyfin's documented
conventions conflict (E21), and the candidate tries to satisfy both at once:

```
Robin Hood (2010) {tmdb-N} - Theatrical {edition-Theatrical}.mkv
```

plus a per-file NFO carrying `<edition>`. Will has Plex Pass, which Plex's editions
require.

## How

Use two small copies of a public-domain film, or any film already owned, in a
scratch library on each player. Do not use the production library. Check that
each player:

- shows one film with two versions, not two films
- labels each version correctly
- matches the film online despite the suffixes

Also try two cuts whose runtimes differ, the way Robin Hood's 155.9 and 140.5
minutes do.

## Done when

- The design's *Editions* section states the naming that works, with the player
  versions it was tested on, and drops the word "candidate".
- Any player that cannot be satisfied is named there, with what it shows
  instead.
