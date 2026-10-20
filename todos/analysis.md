# analysis: the measuring primitives

## Opening prompt

> Build reelbarrow's analysis layer: the functions that measure a file or a raw
> disc copy and return facts. They do not interpret those facts. Read
> `todos/analysis.md`, then *Identity* and step 2 of *The service* in
> `docs/design.md`. Every technique here was measured on real discs between
> 2026-10-03 and 10-05; reproduce the measured behaviour, and do not redesign it.

## Scope

Pure measurement, unit-tested, with no knowledge of jobs, plans or the library:

| function | method in the design | notes |
|---|---|---|
| probe | `ffprobe -show_format -show_streams -show_chapters -of json` | parsed into typed records; the raw JSON is kept, because it becomes a fixture |
| video hash | `ffmpeg -map 0:v -c copy -f md5 -` | exact-duplicate test (*Title identity* 1) |
| fingerprint | `fpcalc -raw -length 0` on the first audio track at 11,025 Hz mono | **verify that the decoded duration matches the container's before trusting it**: one fingerprint came back truncated over `kubectl exec` |
| alignment | map every 15 s window of the shorter onto the longer by voting on frame offsets | returns coverage and the offset series, so a caller can test for a monotonic offset (*Title identity* 2) |
| Blu-ray nav hash | SHA-1 over `BDMV/PLAYLIST/*`, `BDMV/index.bdmv`, `BDMV/MovieObject.bdmv`, path + bytes | disc identity; **never** `CERTIFICATE/id.bdmv` |
| Blu-ray completeness hash | SHA-1 over relative path + size of every file under `BDMV/` | tells a complete copy from a partial one |
| DVD image structure | long-title list (duration, chapters) from an ISO or `VIDEO_TS` | the structural identity check for images, because pydvdid cannot match a re-authored image (*Case 9*) |

Whisper transcription belongs to [episode-matching](episode-matching.md), not here.

## Starting material

Prototypes from the design sessions are in `captures/design/` in Will's
checkout (gitignored, not on GitHub):

- `robinhood/align.py`: the alignment that produced the 94.9% / 0.0% table, and
  `robinhood/*.fp`, the fingerprints it ran on
- `bdfp.py`: the Blu-ray nav and completeness hashing behind experiment E11
- `survey.py`: the share inventory

Port their logic and do not import them. Their `.fp` files make good first test
inputs: Robin Hood's two cuts must align at about 95% coverage with a rising
offset, and the Rescuers feature against `title_71` at 0%.

## Decisions for this session

- Whether to call chromaprint through `fpcalc` or a binding. `fpcalc` is in both
  the devenv and the image, and is what was measured; a binding needs a reason.
- How the alignment is tested without shipping copyrighted audio. Fingerprints
  are not audio, and cannot be turned back into it; check that claim before
  relying on it.

## Done when

- Each function has tests on committed inputs, and `devenv test` passes.
- Alignment reproduces the design's four-row table from the captured
  fingerprints, within a point of each figure.
- The duration check rejects a deliberately truncated input.
