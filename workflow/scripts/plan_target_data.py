"""Plan target electricity-demand data acquisition."""

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

import geopandas as gpd
import pandas as pd
from _schemas import Shapes
from _source_capabilities import (
    as_utc,
    intersect_source_temporal_scope,
    uncovered_temporal_intervals,
)

if TYPE_CHECKING:
    snakemake: Any


TARGET_DATA_PLAN_VERSION = 2


_as_utc = as_utc


def effective_source_temporal_scope(
    metadata: Mapping[str, Any], *, start: object, end: object
) -> dict[str, str] | None:
    """Return the intersection of requested and source temporal scopes."""
    effective_scope = intersect_source_temporal_scope(metadata, start=start, end=end)

    if effective_scope is None:
        return None

    effective_start, effective_end = effective_scope

    return {"start": effective_start.isoformat(), "end": effective_end.isoformat()}


def supported_target_contexts(
    target_contexts: Sequence[str], *, metadata: Mapping[str, Any]
) -> list[str]:
    """Return target contexts supported by one source."""
    contexts = metadata.get("contexts")

    # Missing or empty contexts means that the source declares
    # no geographic restriction.
    if not contexts:
        return list(target_contexts)

    supported = set(contexts)

    return [context for context in target_contexts if context in supported]


def build_target_data_plan(
    *,
    target_contexts: Sequence[str],
    source_names: Sequence[str],
    source_registry: Mapping[str, Mapping[str, Any]],
    temporal_scope: Mapping[str, Any],
) -> dict[str, object]:
    """Build the target-data acquisition plan."""
    target_contexts = sorted(set(target_contexts))

    if not target_contexts:
        raise ValueError("The supplied shapes contain no land-country contexts.")

    source_contexts: dict[str, list[str]] = {}
    source_temporal_scopes: dict[str, dict[str, str] | None] = {}
    active_sources: list[str] = []

    for source_name in source_names:
        if source_name not in source_registry:
            raise ValueError(f"Unsupported electricity-demand source: {source_name!r}.")

        metadata = source_registry[source_name]

        effective_temporal_scope = effective_source_temporal_scope(
            metadata, start=temporal_scope["start"], end=temporal_scope["end"]
        )

        source_temporal_scopes[source_name] = effective_temporal_scope

        if effective_temporal_scope is None:
            source_contexts[source_name] = []
            continue

        contexts = supported_target_contexts(target_contexts, metadata=metadata)

        source_contexts[source_name] = contexts

        if contexts:
            active_sources.append(source_name)

    uncovered_by_context: dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]] = {}

    for context in target_contexts:
        intervals = []

        for source_name, contexts in source_contexts.items():
            if context not in contexts:
                continue

            source_temporal_scope = source_temporal_scopes[source_name]

            if source_temporal_scope is None:
                continue

            intervals.append(
                (source_temporal_scope["start"], source_temporal_scope["end"])
            )

        gaps = uncovered_temporal_intervals(
            intervals, start=temporal_scope["start"], end=temporal_scope["end"]
        )

        if gaps:
            uncovered_by_context[context] = gaps

    if uncovered_by_context:
        gap_descriptions = {
            context: [
                f"[{gap_start.isoformat()}, {gap_end.isoformat()})"
                for gap_start, gap_end in gaps
            ]
            for context, gaps in uncovered_by_context.items()
        }

        raise ValueError(
            "Configured electricity-demand sources do not provide "
            "complete temporal coverage for the following target "
            f"context(s): {gap_descriptions}. "
            f"Configured sources: {list(source_names)}."
        )

    return {
        "version": TARGET_DATA_PLAN_VERSION,
        "target_contexts": target_contexts,
        "active_sources": active_sources,
        "source_contexts": source_contexts,
        "source_temporal_scopes": source_temporal_scopes,
    }


def write_target_data_plan(
    *, plan: Mapping[str, object], output_path: str | Path
) -> None:
    """Write the target-data acquisition plan as JSON."""
    output_path = Path(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(plan, file, indent=2)


def main(snakemake: Any) -> None:
    """Build and write the target-data acquisition plan."""
    shapes = gpd.read_parquet(snakemake.input.shapes)
    shapes = Shapes.validate(shapes)

    land_shapes = shapes.loc[shapes["shape_class"] == "land"]

    target_contexts = land_shapes["country_id"].drop_duplicates().tolist()

    plan = build_target_data_plan(
        target_contexts=target_contexts,
        source_names=snakemake.params.source_names,
        source_registry=snakemake.params.source_registry,
        temporal_scope=snakemake.params.temporal_scope,
    )

    write_target_data_plan(plan=plan, output_path=snakemake.output.plan)


if __name__ == "__main__":
    main(snakemake)
