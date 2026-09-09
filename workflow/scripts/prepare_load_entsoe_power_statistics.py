"""Snakemake entry point for preparing ENTSO-E Power Statistics load."""

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from _advanced_execution import get_batch, load_execution_plan
from sources.entsoe_power_statistics.prepare import prepare_entsoe_power_statistics
from tclean import TimeGrid

if TYPE_CHECKING:
    snakemake: Any


def main(snakemake: Any) -> None:
    """Prepare ENTSO-E Power Statistics for the requested workflow period."""
    plan_path = getattr(snakemake.input, "plan", None)

    if plan_path is not None:
        plan = load_execution_plan(plan_path)

        batch = get_batch(
            plan,
            batch_id=snakemake.wildcards.batch_id,
            source="entsoe_power_statistics",
        )

        start = batch["start"]
        end = batch["end"]
        country_codes = list(batch["countries"])

    else:
        start = snakemake.params.temporal_start
        end = snakemake.params.temporal_end
        country_codes = list(snakemake.params.country_codes)

    grid = TimeGrid(start=start, end=end, frequency=snakemake.params.frequency)

    prepare_entsoe_power_statistics(
        input_paths=[Path(path) for path in snakemake.input.annual_files],
        output_path=snakemake.output.load,
        grid=grid,
        country_codes=country_codes,
    )


if __name__ == "__main__":
    sys.stderr = open(snakemake.log[0], "w", buffering=1)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    main(snakemake)
