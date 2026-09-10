"""Plan advanced electricity-demand execution."""

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd
from _advanced_execution import (
    EXECUTION_PLAN_VERSION,
    build_source_batches,
    empty_execution_plan,
    index_batch_ids_by_group,
    index_batch_ids_by_source,
    resolve_required_group_ids,
    serialize_batch,
)
from _tclean_config import (
    build_advanced_rules,
    build_all_constructed_source_periods,
    build_basic_rules,
    build_source_capabilities,
    build_time_grid,
    filter_source_requests_by_temporal_scope,
    get_advanced_source_definitions,
)
from tclean.gap_filling import (
    build_auxiliary_acquisition_requirements,
    build_auxiliary_source_requests,
    select_active_advanced_rules,
)

if TYPE_CHECKING:
    snakemake: Any


def build_advanced_execution_plan(
    *,
    target_contexts: Sequence[str],
    temporal_scope: Mapping[str, Any],
    gap_filling_config: Mapping[str, Any],
    source_names: Sequence[str],
    source_registry: Mapping[str, Mapping[str, Any]],
) -> dict[str, object]:
    """Build the advanced Snakemake execution manifest."""
    if gap_filling_config["mode"] != "advanced":
        return empty_execution_plan()

    grid = build_time_grid(temporal_scope)

    advanced_rules = build_advanced_rules(gap_filling_config)

    active_rules = select_active_advanced_rules(
        advanced_rules, target_contexts=target_contexts, grid=grid
    )

    if active_rules.empty:
        return empty_execution_plan()

    source_definitions = get_advanced_source_definitions(gap_filling_config)

    active_source_names = _get_active_source_names(active_rules)

    constructed_source_periods = build_all_constructed_source_periods(
        gap_filling_config, source_names=active_source_names
    )

    requirements = build_auxiliary_acquisition_requirements(
        list(constructed_source_periods.values()),
        basic_rules=build_basic_rules(gap_filling_config),
        grid=grid,
        basic_cleaning_enabled=(
            gap_filling_config["advanced"]["auxiliary_data"]["basic_cleaning"][
                "enabled"
            ]
        ),
    )

    source_capabilities = build_source_capabilities(
        source_names, source_registry=source_registry
    )

    requests = build_auxiliary_source_requests(
        requirements, source_capabilities=source_capabilities, grid=grid
    )

    requests = filter_source_requests_by_temporal_scope(
        requests, requirements=requirements, source_registry=source_registry
    )

    raw_batches = build_source_batches(requests)

    batches = [serialize_batch(batch) for batch in raw_batches]

    rules = _build_rule_manifest(
        active_rules,
        source_definitions=source_definitions,
        constructed_source_periods=(constructed_source_periods),
        batches=raw_batches,
    )

    constructed_profile_rule_names = [
        rule_name
        for rule_name, rule in rules.items()
        if rule["method"] == "construct_from_sources"
    ]

    external_profile_files = _build_external_profile_files(
        active_rules, source_definitions=source_definitions
    )

    return {
        "version": EXECUTION_PLAN_VERSION,
        "active_rule_names": (active_rules["rule_name"].tolist()),
        "rules": rules,
        "batches": batches,
        "batch_ids_by_source": (index_batch_ids_by_source(batches)),
        "groups": (index_batch_ids_by_group(batches)),
        "constructed_profile_rule_names": (constructed_profile_rule_names),
        "external_profile_files": (external_profile_files),
    }


def _get_active_source_names(active_rules: pd.DataFrame) -> list[str]:
    """Return referenced advanced sources in rule order."""
    source_names: list[str] = []

    for source_name in active_rules["source"]:
        if pd.isna(source_name):
            continue

        source_name = str(source_name)

        if source_name not in source_names:
            source_names.append(source_name)

    return source_names


def _build_rule_manifest(
    active_rules: pd.DataFrame,
    *,
    source_definitions: Mapping[str, Mapping[str, Any]],
    constructed_source_periods: Mapping[str, pd.DataFrame],
    batches: Sequence[Mapping[str, object]],
) -> dict[str, dict[str, object]]:
    """Build manifest metadata for active advanced rules."""
    rules: dict[str, dict[str, object]] = {}

    for rule in active_rules.itertuples(index=False):
        source_name = None if pd.isna(rule.source) else str(rule.source)

        required_group_ids: list[str] = []

        if source_name is not None and rule.method == "construct_from_sources":
            if source_name not in constructed_source_periods:
                raise ValueError(
                    "No constructed-source periods were "
                    f"planned for advanced source "
                    f"{source_name!r}."
                )

            required_group_ids = resolve_required_group_ids(
                batches, source_periods=(constructed_source_periods[source_name])
            )

        rules[str(rule.rule_name)] = {
            "method": str(rule.method),
            "source": source_name,
            "context": str(rule.context),
            "start": pd.Timestamp(rule.start).isoformat(),
            "end": pd.Timestamp(rule.end).isoformat(),
            "scope": str(rule.scope),
            "required_group_ids": (required_group_ids),
        }

    return rules


def _build_external_profile_files(
    active_rules: pd.DataFrame, *, source_definitions: Mapping[str, Mapping[str, Any]]
) -> dict[str, str]:
    """Map active external-profile rules to their files."""
    result: dict[str, str] = {}

    for rule in active_rules.itertuples(index=False):
        if rule.method != "external_profile":
            continue

        if pd.isna(rule.source):
            raise ValueError(f"External-profile rule {rule.rule_name!r} has no source.")

        source_name = str(rule.source)

        if source_name not in source_definitions:
            raise ValueError(f"Unknown advanced source {source_name!r}.")

        definition = source_definitions[source_name]

        if definition["method"] != "external_profile":
            raise ValueError(
                f"Advanced source {source_name!r} is not an external-profile source."
            )

        result[source_name] = str(definition["file"])

    return result


def write_execution_plan(
    *, plan: Mapping[str, object], output_path: str | Path
) -> None:
    """Write the execution manifest as JSON."""
    output_path = Path(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(plan, file, indent=2)


def main(snakemake: Any) -> None:
    """Build and write the advanced execution manifest."""
    demand = pd.read_parquet(snakemake.input.demand)

    target_contexts = list(demand.columns)

    plan = build_advanced_execution_plan(
        target_contexts=target_contexts,
        temporal_scope=snakemake.params.temporal_scope,
        gap_filling_config=snakemake.params.gap_filling,
        source_names=snakemake.params.source_names,
        source_registry=snakemake.params.source_registry,
    )

    write_execution_plan(plan=plan, output_path=snakemake.output.plan)


if __name__ == "__main__":
    main(snakemake)
