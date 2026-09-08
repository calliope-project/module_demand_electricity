"""Translate Modelblocks electricity-demand configuration to T-Clean inputs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd
from _source_capabilities import (
    intersect_source_temporal_scope,
    uncovered_temporal_intervals,
)
from tclean import TimeGrid


def build_time_grid(temporal_scope: Mapping[str, Any]) -> TimeGrid:
    """Build the canonical T-Clean time grid."""
    return TimeGrid(
        start=temporal_scope["start"],
        end=temporal_scope["end"],
        frequency=temporal_scope["frequency"],
    )


def build_data_quality_tests(
    data_quality_config: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Translate module data-quality configuration to T-Clean tests."""
    tests: list[dict[str, Any]] = []

    for configured_test in data_quality_config["tests"]:
        test = dict(configured_test)

        countries = test.pop("countries", None)
        if countries is not None:
            test["contexts"] = list(countries)

        tests.append(test)

    return tests


def build_basic_rules(gap_filling_config: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return configured basic-cleaning rules for T-Clean."""
    if gap_filling_config["mode"] == "off":
        return []

    return [dict(rule) for rule in gap_filling_config["basic"]["rules"]]


def build_advanced_rules(gap_filling_config: Mapping[str, Any]) -> pd.DataFrame:
    """Build the canonical T-Clean advanced-rule table."""
    columns = ["rule_name", "method", "source", "context", "start", "end", "scope"]

    if gap_filling_config["mode"] != "advanced":
        return pd.DataFrame(columns=columns)

    advanced_config = gap_filling_config["advanced"]
    source_definitions = advanced_config["sources"]

    rows: list[dict[str, object]] = []

    for rule in advanced_config["rules"]:
        source_name = rule.get("source")

        if source_name is None:
            method = "leave_missing"
        else:
            if source_name not in source_definitions:
                raise ValueError(
                    "Advanced rule "
                    f"{rule['name']!r} references unknown source "
                    f"{source_name!r}."
                )

            method = source_definitions[source_name]["method"]

        rows.append(
            {
                "rule_name": rule["name"],
                "method": method,
                "source": source_name,
                "context": rule["country"],
                "start": pd.to_datetime(rule["start"], utc=True),
                "end": pd.to_datetime(rule["end"], utc=True),
                "scope": rule["scope"],
            }
        )

    return pd.DataFrame(rows, columns=columns)


def build_constructed_source_periods(
    source_definition: Mapping[str, Any],
) -> pd.DataFrame:
    """Build T-Clean source periods for one constructed source."""
    if source_definition["method"] != "construct_from_sources":
        raise ValueError("Source definition is not a construct_from_sources source.")

    return _build_source_periods(source_definition["periods"])


def build_scaling_source_periods(
    source_definition: Mapping[str, Any],
) -> pd.DataFrame | None:
    """Build scaling source periods for a constructed advanced source."""
    scaling = source_definition.get("scaling")

    if scaling is None:
        return None

    if scaling["method"] != "match_total":
        return None

    return _build_source_periods(scaling["periods"])


def build_all_constructed_source_periods(
    gap_filling_config: Mapping[str, Any], *, source_names: Sequence[str] | None = None
) -> dict[str, pd.DataFrame]:
    """Build source-period tables for configured constructed sources."""
    if gap_filling_config["mode"] != "advanced":
        return {}

    source_definitions = gap_filling_config["advanced"]["sources"]

    if source_names is None:
        selected_names = list(source_definitions)
    else:
        selected_names = list(source_names)

    result: dict[str, pd.DataFrame] = {}

    for source_name in selected_names:
        if source_name not in source_definitions:
            raise ValueError(f"Unknown advanced source {source_name!r}.")

        definition = source_definitions[source_name]

        if definition["method"] != "construct_from_sources":
            continue

        frames = [build_constructed_source_periods(definition)]

        scaling_periods = build_scaling_source_periods(definition)

        if scaling_periods is not None:
            frames.append(scaling_periods)

        result[source_name] = pd.concat(frames, ignore_index=True)

    return result


def build_source_capabilities(
    source_names: Sequence[str], *, source_registry: Mapping[str, Mapping[str, Any]]
) -> pd.DataFrame:
    """Describe which contexts configured providers can supply."""
    if len(source_names) != len(set(source_names)):
        raise ValueError("Configured load source names must be unique.")

    capabilities: list[dict[str, object]] = []

    for source_name in source_names:
        if source_name not in source_registry:
            raise ValueError(f"Unsupported electricity-demand source: {source_name!r}.")

        contexts = source_registry[source_name].get("contexts") or [None]

        capabilities.extend(
            {"source": source_name, "context": context} for context in contexts
        )

    return pd.DataFrame(capabilities, columns=["source", "context"])


def get_advanced_source_definitions(
    gap_filling_config: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Return configured advanced source definitions."""
    if gap_filling_config["mode"] != "advanced":
        return {}

    return gap_filling_config["advanced"]["sources"]


def _build_source_periods(periods: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    """Convert Modelblocks country periods to generic T-Clean periods."""
    return pd.DataFrame(
        [
            {
                "context": period["country"],
                "start": pd.to_datetime(period["start"], utc=True),
                "end": pd.to_datetime(period["end"], utc=True),
                "weight": period["weight"],
            }
            for period in periods
        ],
        columns=["context", "start", "end", "weight"],
    )


def filter_source_requests_by_temporal_scope(
    requests: pd.DataFrame,
    *,
    requirements: pd.DataFrame,
    source_registry: Mapping[str, Mapping[str, Any]],
) -> pd.DataFrame:
    """Clip auxiliary source requests to provider temporal availability."""
    if requests.empty:
        return requests.copy()

    output_columns = list(requests.columns)

    for column in ("group_start", "group_end"):
        if column not in output_columns:
            output_columns.append(column)

    clipped_rows: list[dict[str, object]] = []

    for request in requests.itertuples(index=False):
        row = request._asdict()

        metadata = source_registry[str(request.source)]

        request_start = pd.to_datetime(request.start, utc=True)
        request_end = pd.to_datetime(request.end, utc=True)

        effective_scope = intersect_source_temporal_scope(
            metadata, start=request_start, end=request_end
        )

        if effective_scope is None:
            continue

        effective_start, effective_end = effective_scope

        row["group_start"] = request_start
        row["group_end"] = request_end
        row["start"] = effective_start
        row["end"] = effective_end

        clipped_rows.append(row)

    filtered = pd.DataFrame(clipped_rows, columns=output_columns)

    required_periods = requirements[["context", "start", "end"]].drop_duplicates()

    uncovered: list[dict[str, object]] = []

    for requirement in required_periods.itertuples(index=False):
        context = str(requirement.context)
        required_start = pd.to_datetime(requirement.start, utc=True)
        required_end = pd.to_datetime(requirement.end, utc=True)

        candidates = filtered.loc[
            (filtered["context"] == requirement.context)
            & (filtered["group_start"] == required_start)
            & (filtered["group_end"] == required_end)
        ]

        gaps = uncovered_temporal_intervals(
            [
                (candidate.start, candidate.end)
                for candidate in candidates.itertuples(index=False)
            ],
            start=required_start,
            end=required_end,
        )

        uncovered.extend(
            {
                "context": context,
                "start": gap_start.isoformat(),
                "end": gap_end.isoformat(),
            }
            for gap_start, gap_end in gaps
        )

    if uncovered:
        raise ValueError(
            "Configured auxiliary sources do not provide complete "
            "temporal coverage for required context-period(s): "
            f"{uncovered}."
        )

    return filtered
