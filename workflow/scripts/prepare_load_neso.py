"""Snakemake entry point for NESO demand preparation."""

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from _advanced_execution import get_batch, load_execution_plan
from sources.neso.prepare import prepare_neso
from tclean import TimeGrid

if TYPE_CHECKING:
    snakemake: Any


def main(snakemake: Any) -> None:
    """Prepare NESO demand for the requested workflow period."""
    plan_path = getattr(snakemake.input, "plan", None)

    if plan_path is not None:
        plan = load_execution_plan(plan_path)

        batch = get_batch(plan, batch_id=snakemake.wildcards.batch_id, source="neso")

        start = batch["start"]
        end = batch["end"]
        countries = batch["countries"]
    else:
        start = snakemake.params.start
        end = snakemake.params.end
        countries = snakemake.params.country_codes

    grid = TimeGrid(start=start, end=end, frequency=snakemake.params.frequency)

    prepare_neso(
        input_paths=[Path(path) for path in snakemake.input.annual_files],
        output_path=snakemake.output.load,
        target_index=grid.target_index,
        countries=countries,
    )


if __name__ == "__main__":
    sys.stderr = open(snakemake.log[0], "w", buffering=1)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    main(snakemake)
