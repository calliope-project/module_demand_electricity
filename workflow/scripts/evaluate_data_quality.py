"""Evaluate data quality of constructed electricity demand."""

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd
from _prepared_data import read_prepared_source
from _tclean_config import (
    CONSTRUCTED_SOURCE_NAME,
    build_data_quality_tests,
    build_time_grid,
)
from tclean import TimeGrid
from tclean.data_quality import evaluate

if TYPE_CHECKING:
    snakemake: Any


def main(snakemake: Any) -> None:
    """Evaluate configured data-quality tests."""
    source_names = list(snakemake.params.source_names)
    input_paths = list(snakemake.input.load_inputs)

    grid = build_time_grid(snakemake.params.temporal_scope)

    constructed = read_prepared_source(snakemake.input.demand)

    sources = _build_evaluation_sources(
        constructed, source_names=source_names, input_paths=input_paths, grid=grid
    )

    tests = build_data_quality_tests(snakemake.params.data_quality)

    evaluation = evaluate(sources, tests=tests, grid=grid)

    evaluation.failures.to_parquet(snakemake.output.failures, index=False)

    evaluation.issues.to_parquet(snakemake.output.issues, index=False)


def _build_evaluation_sources(
    constructed: pd.DataFrame,
    *,
    source_names: Sequence[str],
    input_paths: Sequence[str | Path],
    grid: TimeGrid,
) -> dict[str, pd.DataFrame]:
    """Build aligned sources for data-quality evaluation."""
    if len(input_paths) != len(source_names):
        raise ValueError(
            "The number of prepared load inputs must match the "
            "number of configured load sources."
        )

    if CONSTRUCTED_SOURCE_NAME in source_names:
        raise ValueError(
            f"{CONSTRUCTED_SOURCE_NAME!r} is reserved for constructed demand."
        )

    providers = {
        source_name: read_prepared_source(path).reindex(
            index=grid.target_index, columns=constructed.columns
        )
        for source_name, path in zip(source_names, input_paths, strict=True)
    }

    return {CONSTRUCTED_SOURCE_NAME: constructed, **providers}


if __name__ == "__main__":
    main(snakemake)
