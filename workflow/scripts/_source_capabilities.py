"""Shared source-capability helpers for electricity-demand planning."""

from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd


def as_utc(value: object) -> pd.Timestamp:
    """Interpret naive timestamps as UTC and convert aware timestamps to UTC."""
    timestamp = pd.Timestamp(value)

    if timestamp.tzinfo is None:
        return timestamp.tz_localize("UTC")

    return timestamp.tz_convert("UTC")


def intersect_source_temporal_scope(
    metadata: Mapping[str, Any], *, start: object, end: object
) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    """Return the intersection of a request and one source's temporal scope."""
    temporal_scope = metadata.get("temporal_scope") or {}

    effective_start = as_utc(start)
    effective_end = as_utc(end)

    source_start = temporal_scope.get("start")
    source_end = temporal_scope.get("end")

    if source_start is not None:
        effective_start = max(effective_start, as_utc(source_start))

    if source_end is not None:
        effective_end = min(effective_end, as_utc(source_end))

    if effective_start >= effective_end:
        return None

    return effective_start, effective_end


def uncovered_temporal_intervals(
    intervals: Sequence[tuple[object, object]], *, start: object, end: object
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Return gaps in a required period not covered by any supplied interval."""
    required_start = as_utc(start)
    required_end = as_utc(end)

    covered_intervals = sorted(
        (
            max(as_utc(interval_start), required_start),
            min(as_utc(interval_end), required_end),
        )
        for interval_start, interval_end in intervals
        if (
            as_utc(interval_start) < required_end
            and as_utc(interval_end) > required_start
        )
    )

    gaps: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    cursor = required_start

    for interval_start, interval_end in covered_intervals:
        if interval_end <= cursor:
            continue

        if interval_start > cursor:
            gaps.append((cursor, interval_start))

        cursor = max(cursor, interval_end)

        if cursor >= required_end:
            break

    if cursor < required_end:
        gaps.append((cursor, required_end))

    return gaps
