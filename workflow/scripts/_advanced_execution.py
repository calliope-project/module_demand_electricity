"""Build Snakemake execution metadata for advanced demand cleaning."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pandas as pd

EXECUTION_PLAN_VERSION = 2


def build_source_batches(requests: pd.DataFrame) -> list[dict[str, object]]:
    """Group T-Clean source requests into executable provider batches."""
    if requests.empty:
        return []

    required_columns = {"source", "context", "start", "end"}

    missing_columns = required_columns - set(requests.columns)

    if missing_columns:
        raise ValueError(
            "Auxiliary source requests are missing required "
            f"columns: {sorted(missing_columns)}."
        )

    requests = requests.copy()

    if "group_start" not in requests.columns:
        requests["group_start"] = requests["start"]

    if "group_end" not in requests.columns:
        requests["group_end"] = requests["end"]

    batches: list[dict[str, object]] = []

    grouped = requests.groupby(
        ["source", "start", "end", "group_start", "group_end"], sort=False
    )

    for (source, start, end, group_start, group_end), group in grouped:
        start = pd.Timestamp(start)
        end = pd.Timestamp(end)
        group_start = pd.Timestamp(group_start)
        group_end = pd.Timestamp(group_end)

        if end <= start:
            raise ValueError("Auxiliary batch end must be later than its start.")

        if group_end <= group_start:
            raise ValueError("Auxiliary group end must be later than its start.")

        if start < group_start or end > group_end:
            raise ValueError(
                "Auxiliary provider batch must lie within its logical group period."
            )

        countries = sorted(group["context"].drop_duplicates().tolist())

        group_id = build_group_id(start=group_start, end=group_end)

        batch_id = build_batch_id(
            source=str(source),
            start=start,
            end=end,
            countries=countries,
            group_id=group_id,
        )

        batches.append(
            {
                "group_id": group_id,
                "batch_id": batch_id,
                "source": str(source),
                "start": start,
                "end": end,
                "group_start": group_start,
                "group_end": group_end,
                "countries": countries,
            }
        )

    return batches


def serialize_batch(batch: Mapping[str, object]) -> dict[str, object]:
    """Convert one auxiliary batch to JSON-compatible values."""
    start = pd.Timestamp(batch["start"])
    end = pd.Timestamp(batch["end"])
    group_start = pd.Timestamp(batch.get("group_start", start))
    group_end = pd.Timestamp(batch.get("group_end", end))

    if end <= start:
        raise ValueError("Auxiliary batch end must be later than its start.")

    if group_end <= group_start:
        raise ValueError("Auxiliary group end must be later than its start.")

    final_included_time = end - pd.Timedelta(nanoseconds=1)

    return {
        **batch,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "group_start": group_start.isoformat(),
        "group_end": group_end.isoformat(),
        "years": list(range(start.year, final_included_time.year + 1)),
    }


def build_group_id(*, start: pd.Timestamp, end: pd.Timestamp) -> str:
    """Build a deterministic identifier for one auxiliary period."""
    return f"{start.strftime('%Y%m%dT%H%M')}__{end.strftime('%Y%m%dT%H%M')}"


def build_batch_id(
    *,
    source: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    countries: Sequence[str],
    group_id: str | None = None,
) -> str:
    """Build a compact deterministic identifier for one provider batch."""
    batch_key_data = {
        "source": str(source),
        "start": pd.Timestamp(start).isoformat(),
        "end": pd.Timestamp(end).isoformat(),
        "countries": sorted(str(country) for country in countries),
    }

    if group_id is not None:
        batch_key_data["group_id"] = str(group_id)

    batch_key = json.dumps(batch_key_data, sort_keys=True, separators=(",", ":"))

    return hashlib.sha1(batch_key.encode("utf-8")).hexdigest()[:16]


def index_batch_ids_by_source(
    batches: Sequence[Mapping[str, object]],
) -> dict[str, list[str]]:
    """Index planned batch identifiers by provider source."""
    result: dict[str, list[str]] = {}

    for batch in batches:
        source = str(batch["source"])
        batch_id = str(batch["batch_id"])

        result.setdefault(source, []).append(batch_id)

    return result


def index_batch_ids_by_group(
    batches: Sequence[Mapping[str, object]],
) -> dict[str, list[str]]:
    """Index planned batch identifiers by auxiliary period group."""
    result: dict[str, list[str]] = {}

    for batch in batches:
        group_id = str(batch["group_id"])
        batch_id = str(batch["batch_id"])

        result.setdefault(group_id, []).append(batch_id)

    return result


def resolve_required_group_ids(
    batches: Sequence[Mapping[str, object]], *, source_periods: pd.DataFrame
) -> list[str]:
    """Resolve source periods to acquired auxiliary period groups."""
    if source_periods.empty:
        return []

    required_columns = {"context", "start", "end"}

    missing_columns = required_columns - set(source_periods.columns)

    if missing_columns:
        raise ValueError(
            "Advanced source periods are missing required "
            f"columns: {sorted(missing_columns)}."
        )

    group_ids: list[str] = []

    for period in source_periods.itertuples(index=False):
        start = pd.Timestamp(period.start)
        end = pd.Timestamp(period.end)

        matching_group_ids = {
            str(batch["group_id"])
            for batch in batches
            if (
                period.context in batch["countries"]
                and pd.Timestamp(batch.get("group_start", batch["start"])) <= start
                and pd.Timestamp(batch.get("group_end", batch["end"])) >= end
            )
        }

        if len(matching_group_ids) != 1:
            raise ValueError(
                "Expected exactly one auxiliary group "
                f"covering context {period.context!r} "
                f"from {start} to {end}, found "
                f"{sorted(matching_group_ids)}."
            )

        group_id = next(iter(matching_group_ids))

        if group_id not in group_ids:
            group_ids.append(group_id)

    return group_ids


def empty_execution_plan() -> dict[str, object]:
    """Return an empty advanced execution manifest."""
    return {
        "version": EXECUTION_PLAN_VERSION,
        "active_rule_names": [],
        "rules": {},
        "batches": [],
        "batch_ids_by_source": {},
        "groups": {},
        "constructed_profile_rule_names": [],
        "external_profile_files": {},
    }


def load_execution_plan(path: str | Path) -> dict[str, Any]:
    """Load one compiled advanced execution plan."""
    with open(path, encoding="utf-8") as file:
        plan = json.load(file)

    if not isinstance(plan, dict):
        raise TypeError("Advanced execution plan must contain a JSON object.")

    if plan.get("version") != EXECUTION_PLAN_VERSION:
        raise ValueError(
            "Unsupported advanced execution plan version: "
            f"{plan.get('version')!r}. "
            f"Expected {EXECUTION_PLAN_VERSION}."
        )

    return plan


def get_batch(
    plan: Mapping[str, Any], *, batch_id: str, source: str | None = None
) -> Mapping[str, Any]:
    """Return exactly one compiled auxiliary batch."""
    matches = [
        batch
        for batch in plan["batches"]
        if (
            batch["batch_id"] == batch_id
            and (source is None or batch["source"] == source)
        )
    ]

    if len(matches) != 1:
        source_text = f" for source {source!r}" if source is not None else ""

        raise ValueError(
            "Expected exactly one auxiliary batch "
            f"{batch_id!r}{source_text}, "
            f"found {len(matches)}."
        )

    return matches[0]
