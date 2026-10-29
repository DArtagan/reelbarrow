"""What a title plays from its disc, and how much of that other titles play.

A title is a sequence of segments, each a stretch of one source on the disc: a
Blu-ray clip between two times, or a run of sectors in a DVD title set. Two
titles play the same material exactly where their segments overlap on one
source, so a play-all is told from its episodes, or a documentary from its
parts, without decoding anything. Length alone tells neither.

These are the measurements the deployment's ARM makes before transcoding, to
the same definitions, so a job without a stamp's `duplicates` is judged by
them as one with it was.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Segment:
    # The clip ("00001") or title set (1) the segment plays from.
    source: str | int
    # Its extent there, end exclusive, in the source's own units: 45 kHz ticks
    # of a clip, or sectors of a title set.
    start: int
    end: int
    # Seconds it plays for.
    seconds: float


def units(segments: Iterable[Segment]) -> int:
    return sum(s.end - s.start for s in segments)


def covered(segments: Sequence[Segment], others: Iterable[Sequence[Segment]]) -> int:
    """How much of `segments`, in its own units, at least one of `others` plays."""
    others = [s for other in others for s in other]
    total = 0
    for segment in segments:
        reached = segment.start
        for start, end in sorted(_overlaps(segment, others)):
            start = max(start, reached)
            if end > start:
                total += end - start
                reached = end
    return total


def own(
    segments: Sequence[Segment], others: Iterable[Sequence[Segment]]
) -> tuple[Segment, ...]:
    """`segments` less whatever any of `others` also plays."""
    others = [s for other in others for s in other]
    result = []
    for segment in segments:
        reached = segment.start
        spans = sorted((o.start, o.end) for o in others if o.source == segment.source)
        for start, end in [*spans, (segment.end, segment.end)]:
            stop = min(start, segment.end)
            if stop > reached:
                result.append(_cut(segment, reached, stop))
            reached = max(reached, end)
    return tuple(result)


def span(
    part: Sequence[Segment], whole: Sequence[Segment]
) -> tuple[float, float] | None:
    """The first and last second of `whole` that plays any of `part`."""
    first = last = None
    elapsed = 0.0
    for segment in whole:
        rate = _rate(segment)
        for start, end in _overlaps(segment, part):
            begins = elapsed + (start - segment.start) * rate
            ends = elapsed + (end - segment.start) * rate
            first = begins if first is None else min(first, begins)
            last = ends if last is None else max(last, ends)
        elapsed += segment.seconds
    return None if first is None else (first, last)


def _overlaps(segment: Segment, others: Iterable[Segment]) -> Iterable[tuple[int, int]]:
    for other in others:
        start, end = max(segment.start, other.start), min(segment.end, other.end)
        if other.source == segment.source and end > start:
            yield start, end


def _cut(segment: Segment, start: int, end: int) -> Segment:
    return Segment(segment.source, start, end, (end - start) * _rate(segment))


def _rate(segment: Segment) -> float:
    # Seconds per unit. A DVD cell's sectors carry no time of their own, so a
    # part of one is taken to play for its share of the cell's seconds.
    width = segment.end - segment.start
    return segment.seconds / width if width else 0.0
