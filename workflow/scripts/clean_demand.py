"""Combine and basic-clean prepared electricity-demand sources."""

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd
from _prepared_data import read_prepared_source
from _tclean_config import build_basic_rules, build_time_grid
from tclean.gap_filling import (
    build_cleaning_method_ranks,
    build_gap_report,
    derive_cleaning_method_rank,
    fill_gaps,
)

if TYPE_CHECKING:
    snakemake: Any


logger = logging.getLogger(__name__)


def main(snakemake: Any) -> None:
    """Run the main electricity-demand cleaning stage."""
    source_names = list(snakemake.params.source_names)

    input_paths = list(snakemake.input.load_inputs)

    if len(input_paths) != len(source_names):
        raise ValueError(
            "The number of prepared load inputs must match the "
            "number of configured load sources."
        )

    sources = {
        source_name: read_prepared_source(path)
        for source_name, path in zip(source_names, input_paths, strict=True)
    }

    target_contexts = _read_target_contexts(snakemake.input.target_plan)

    grid = build_time_grid(snakemake.params.temporal_scope)

    sources = {
        source_name: data.reindex(index=grid.target_index, columns=target_contexts)
        for source_name, data in sources.items()
    }

    basic_rules = build_basic_rules(snakemake.params.gap_filling)

    (cleaned, data_source, cleaning_method) = fill_gaps(
        sources, grid=grid, basic_rules=basic_rules
    )

    basic_rule_names = [rule["name"] for rule in basic_rules]

    cleaning_method_ranks = build_cleaning_method_ranks(
        source_names, basic_rule_names=basic_rule_names
    )

    cleaning_method_rank = derive_cleaning_method_rank(
        cleaning_method=cleaning_method, ranks=cleaning_method_ranks
    )

    gap_report = build_gap_report(
        cleaned, grid=grid, enabled=(snakemake.params.gap_filling["mode"] == "advanced")
    )

    cleaned.to_parquet(snakemake.output.demand)

    data_source.to_parquet(snakemake.output.data_source)

    cleaning_method.to_parquet(snakemake.output.cleaning_method)

    cleaning_method_rank.to_parquet(snakemake.output.cleaning_method_rank)

    gap_report.to_parquet(snakemake.output.gap_report, index=False)

    _log_source_counts(data_source)

    _log_cleaning_method_counts(cleaning_method)

    _log_gap_report(gap_report)


def _read_target_contexts(path: str | Path) -> list[str]:
    """Read the planned target contexts for one shape."""
    with open(path, encoding="utf-8") as file:
        plan = json.load(file)

    return [str(context) for context in plan["target_contexts"]]


def _log_source_counts(data_source: pd.DataFrame) -> None:
    """Log observed-value counts by source."""
    counts = data_source.stack().value_counts()

    if counts.empty:
        logger.info("No observed source values were recorded.")
        return

    for source_name, count in counts.items():
        logger.info("%s supplied %s values.", source_name, int(count))


def _log_cleaning_method_counts(cleaning_method: pd.DataFrame) -> None:
    """Log value counts by cleaning method."""
    counts = cleaning_method.stack().value_counts()

    if counts.empty:
        logger.info("No cleaning methods were recorded.")
        return

    for method, count in counts.items():
        logger.info("%s supplied %s values.", method, int(count))


def _log_gap_report(gap_report: pd.DataFrame) -> None:
    """Log unresolved-gap counts by context."""
    if gap_report.empty:
        logger.info("No unresolved gaps remain after basic cleaning.")
        return

    logger.info("Gap report contains %s contiguous unresolved gaps.", len(gap_report))

    for context, context_gaps in gap_report.groupby("context"):
        total_duration = context_gaps["gap_duration"].sum()

        logger.info(
            "%s has %s unresolved gaps covering %s.",
            context,
            len(context_gaps),
            total_duration,
        )


if __name__ == "__main__":
    main(snakemake)
