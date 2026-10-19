# episode-matching: which episode is this title

## Opening prompt

> Build reelbarrow's TV episode identification and its evaluation harness, and
> file *The Sylvester & Tweety Mysteries* season 1 with them. Read
> `todos/episode-matching.md`, then *Title identity* (tool 3), *The LLM*,
> *Confidence* (the episode row and *The episode matcher*) and all of *Testing*
> in `docs/design.md`.

## Scope

1. **Transcripts.** `whisper.cpp` with `ggml-base.en`, over two windows per title
   (to get past a cold open or recap). 4-minute clips took 32 s for 8 on 8 desktop
   threads. Measure speed on worker-0's CPU before choosing window lengths; it
   has never been measured. The model goes in the image or on the data PVC, not
   fetched at runtime.
2. **Reference text** from several sources: Wikipedia episode lists, TMDB, IMDb
   plots, and OpenSubtitles where its rate limit allows. Gathering this is a
   first-class step: in E27 it moved accuracy from 8/13 to 13/13.
3. **The matcher.** Claude through a pay-as-you-go API key (Will, 2026-10-05), behind
   one small interface. It returns a one-to-one mapping with per-item confidence
   and quoted evidence. The JSON schema restricts episode answers to an `enum` of
   valid IDs; E28 broke a freer format. The default model is whichever the
   evaluation picks, starting with the current Haiku.
4. **The second signal and the gate.** Filing is automatic only if the matcher's
   mapping agrees with an independent signal (TF-IDF or embedding assignment,
   reference runtime, or the case photo's list) and is one-to-one. A model's
   confidence is never the gate: one title was wrong in all four runs at
   0.75–0.85.
5. **Play-alls and duplicates.** Per *Confidence*: drop both play-all
   transcodes, keep their raw, and treat job 33 as job 22's duplicate.
6. **The Inspect harness** (layer 2): datasets of whole decisions; reelbarrow's
   own solver; a scorer of the **gate's outcome**; 10 epochs, with a reducer that
   fails a sample if **any** epoch misfiles. The reducer behaviour has not been
   exercised (E29); prove it on a sample known to misfile.
7. **A bigger eval set**, built from labelled TV already in the library (Witch
   Hunter Robin, Miss Fisher, Leverage, NOVA), with a held-out split. Spot-check
   NOVA's ground truth first; some of those filings were wrong.

Prototypes from the design sessions (transcripts, synopses, prompts, the scorer)
are in Will's vulcanus-proxmox checkout under
`captures/video-library-ingest/tweety/`. They are gitignored and not on GitHub.

## Secrets

The Anthropic API key, with a spend cap set in the Console, goes into
vulcanus-proxmox's reelbarrow secret.

## Done when

- The held-out split shows **zero** any-epoch misfiles. The automation rate
  measured there is written into the design as the honest estimate.
- All 13 episodes play in Plex as S01E01–E13, and a spot-check of each opening
  matches its title.
