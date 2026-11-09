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

## Identity: the disc's name and the runtime (proposed, not yet decided)

Nothing on the share is evidence of identity by its name (`AGENTS.md`), and
that includes a folder name chosen by hand. Plex's match (E16: 91 of 96
online-matched) came from the folder's name, so it isn't independent of it
either. A name may *propose* a candidate; the evidence has to come from
elsewhere.

The proposed bar is the film row of *Confidence* as it stands: an
identification from the **disc's own name**, and exactly one title within ±3%
of TMDB's runtime. A disc's name is set when it is mastered, not by whoever
filed it, and it is what ARM's identification starts from (the label, through
OMDb). Under this bar the `AGENTS.md` rule stays as written. Will called the
choice *"very tough"*; settle it with him before building. The alternatives
were measured only as far as below.

**Measured 2026-11-09**, read-only from the reelbarrow pod over the 105 folders
in `/video/movies`. The scripts and results are in
`captures/library-identity/` in Will's checkout, gitignored.

- **Runtime.** The longest file outside `raw/` and `extras/` that isn't a
  trailer, against the `<runtime>` in the entry's NFO, which is TMDB's for the
  NFO's ID. 78 within ±3%, 4 within 10% (*Attack the Block*, *On Any
  Sunday*, *Sinbad*, *Sintel*), 7 beyond, 5 with no runtime in the NFO, 12
  with no transcode to measure. Of the 7 beyond, the three *Lord of the Rings*
  films are each split across two files (case 4), *Guns, Germs and Steel* is a
  three-part series, *Animusic 2* and *Phil Collins* are a performance and a
  concert, and *X-Men: First Class* is 15% long, unexplained.
- **What an entry records.** 103 of 105 have an NFO with an IMDb or TMDB ID;
  22 carry `{tmdb-N}` in the folder name. *2022 Laguna Seca* and *Porter
  Robinson – Worlds* have neither.
- **The disc's name**, from the headers alone, nothing mounted:
  - **79 ISOs**: 74 DVD images with an ISO 9660 volume label, 5 UDF-only
    Blu-ray images with a UDF volume label. 72 name a film
    (`SHREK_THE_THIRD`, `NARNIA_1_LION_WITCH_AND_WARDROBE`); 7 are cryptic or
    generic (`PI30NNW1`, `PRE0NNW1`, `PR41NNE1`, `GS_DVD`,
    `VIDEO_DVD`, `CDROM` twice).
  - **The Blu-ray embedded name** in `BDMV/META/DL/bdmt_eng.xml`: present in
    all 4 `BDMV` folders (*Pacific Rim*, *Quantum of Solace*, *Skyfall*,
    *"MARVEL'S THOR: RAGNAROK"*), and found in 2 of the 5 UDF ISOs by scanning
    their first 0.5–1 GB, among them *On Stranger Tides*, whose label is
    `PR41NNE1`.
  - **MakeMKV's title tag** in the 12 MKVs under `raw/`: only *Django
    Unchained* and *Dune*. The rest, ARM-style `C1_t00.mkv`, have none.
- **Both together: 57 of 105** have the runtime within ±3% and a disc name
  that identifies the film, judged by eye rather than by a TMDB search of the
  normalised name, which the rule itself would use. About 5 more could pass
  once the runtime is measured from the disc where an entry has only an ISO
  (three *Pirates of the Caribbean*, *The Pixar Shorts*), so about 62 is this
  bar's ceiling.
- **What remains.** 21 pass the runtime with no disc name to check: 13 are
  2024 `{tmdb-N}` entries with no raw or untitled raw MKVs (*Dredd*,
  *Gladiator*, *The Shawshank Redemption*…), 2 have generic labels (*My
  Neighbor Totoro*, *Redline*), and 6 have no disc (*Ip Man*, *Summer Wars*…).
  15 have a disc name but no runtime pass, mostly the split films, series,
  concerts and shorts above.
- **The DVD CRC64.** Only 18 of the 74 DVD images kept the disc's own file
  timestamps (*The Matrix*'s read 1999-07-30); 56 were re-stamped when the
  image was made, one timestamp for every file, as Shrek's was (E24). pydvdid
  can match a pressed disc only for the 18, which would join a later ARM
  re-rip of the same disc by `crc_id`. Computing it from an unmounted ISO is
  untested.

**Worth a look by hand**, found by these measurements: *The Return of the
King*'s folder holds an ISO labelled `FELLOWSHIPOFTHEKING1` beside
`RETURNOFTHEKING2`, either a label quirk or a *Fellowship* disc in the wrong
folder; and *X-Men: First Class*'s 15% surplus.

## Open questions

- **The bar above**, and what becomes of the entries it can't pass: review,
  or a content signal first (a title card read by a vision model, or a
  dialogue window against OpenSubtitles), neither measured.
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
