"""Validate semantic constraints of the module configuration."""

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd
from _tclean_config import (
    build_advanced_rules,
    build_basic_rules,
    build_constructed_source_periods,
    build_scaling_source_periods,
    build_time_grid,
)
from tclean import TimeGrid
from tclean.gap_filling import validate_basic_rules

if TYPE_CHECKING:
    snakemake: Any


def validate_temporal_config_semantics(config: Mapping[str, Any]) -> None:
    """Validate temporal configuration semantics."""
    build_time_grid(config["temporal_scope"])


def validate_gap_filling_config_semantics(config: Mapping[str, Any]) -> None:
    """Validate gap-filling configuration semantics."""
    gap_filling = config["gap_filling"]

    grid = build_time_grid(config["temporal_scope"])

    _validate_basic_config(gap_filling, grid=grid)

    _validate_advanced_config(gap_filling, grid=grid)


def config_hash(config: Mapping[str, Any]) -> str:
    """Return a deterministic hash of validated configuration."""
    serialised = json.dumps(config, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )

    return hashlib.sha256(serialised).hexdigest()


def _validate_basic_config(gap_filling: Mapping[str, Any], *, grid: TimeGrid) -> None:
    """Validate the configured basic-cleaning rules."""
    mode = gap_filling["mode"]

    if mode == "off":
        return

    rules = build_basic_rules(gap_filling)

    if not rules:
        raise ValueError(
            f"Gap-filling mode is {mode!r}, but no basic cleaning rules are configured."
        )

    validate_basic_rules(rules, grid=grid)


def _validate_advanced_config(
    gap_filling: Mapping[str, Any], *, grid: TimeGrid
) -> None:
    """Validate advanced source definitions and application rules."""
    if gap_filling["mode"] != "advanced":
        return

    advanced = gap_filling["advanced"]

    source_definitions = advanced["sources"]
    rules = advanced["rules"]

    _validate_advanced_rule_periods(rules, grid=grid)

    _validate_advanced_source_definitions(source_definitions, grid=grid)

    # Ensure that the Modelblocks configuration can be represented by the
    # canonical T-Clean advanced-rule contract.
    build_advanced_rules(gap_filling)


def _validate_advanced_rule_periods(
    rules: Sequence[Mapping[str, Any]], *, grid: TimeGrid
) -> None:
    """Validate advanced target periods against the configured grid."""
    for rule in rules:
        try:
            grid.validate_period(
                start=pd.Timestamp(rule["start"]), end=pd.Timestamp(rule["end"])
            )

        except (TypeError, ValueError) as error:
            raise ValueError(
                f"Invalid target period for advanced rule {rule['name']!r}: {error}"
            ) from error


def _validate_advanced_source_definitions(
    source_definitions: Mapping[str, Mapping[str, Any]], *, grid: TimeGrid
) -> None:
    """Validate every configured advanced source."""
    for source_name, definition in source_definitions.items():
        method = definition["method"]

        if method == "construct_from_sources":
            _validate_constructed_source(source_name, definition, grid=grid)

        elif method == "external_profile":
            continue

        else:
            raise ValueError(
                f"Advanced source {source_name!r} uses unsupported method {method!r}."
            )


def _validate_constructed_source(
    source_name: str, definition: Mapping[str, Any], *, grid: TimeGrid
) -> None:
    """Validate one constructed advanced source."""
    source_periods = build_constructed_source_periods(definition)

    _validate_source_periods(
        source_name, source_periods, period_kind="construction", grid=grid
    )

    _validate_equal_period_lengths(
        source_name, source_periods, period_kind="construction", grid=grid
    )

    scaling_periods = build_scaling_source_periods(definition)

    if scaling_periods is None:
        return

    _validate_source_periods(
        source_name, scaling_periods, period_kind="scaling", grid=grid
    )


def _validate_source_periods(
    source_name: str, periods: pd.DataFrame, *, period_kind: str, grid: TimeGrid
) -> None:
    """Validate advanced source periods against the configured grid."""
    for period in periods.itertuples(index=False):
        try:
            grid.validate_period(start=period.start, end=period.end)

        except (TypeError, ValueError) as error:
            raise ValueError(
                f"Invalid {period_kind} period in advanced source "
                f"{source_name!r} for country {period.context!r}: "
                f"{error}"
            ) from error


def _validate_equal_period_lengths(
    source_name: str, periods: pd.DataFrame, *, period_kind: str, grid: TimeGrid
) -> None:
    """Require construction periods to contain equal numbers of values."""
    lengths = {
        len(grid.index_for_period(start=period.start, end=period.end))
        for period in periods.itertuples(index=False)
    }

    if len(lengths) > 1:
        raise ValueError(
            f"All {period_kind} periods in advanced source "
            f"{source_name!r} must contain the same number of "
            "configured time steps."
        )


def write_validation_marker(
    output_path: str | Path, *, validated_config: Mapping[str, Any]
) -> None:
    """Write a marker file when semantic validation succeeds."""
    output_path = Path(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(
            {"valid": True, "config_hash": config_hash(validated_config)},
            file,
            indent=2,
        )


if __name__ == "__main__":
    validation_kind = snakemake.params.validation_kind
    validation_config = snakemake.params.validation_config

    if validation_kind == "temporal":
        validate_temporal_config_semantics(validation_config)

    elif validation_kind == "gap_filling":
        validate_gap_filling_config_semantics(validation_config)

    else:
        raise ValueError(f"Unsupported validation kind {validation_kind!r}.")

    write_validation_marker(snakemake.output[0], validated_config=validation_config)
