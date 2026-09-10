"""Snakemake entry point for preparing OPSD demand data."""

import sys
from typing import TYPE_CHECKING, Any

from _advanced_execution import get_batch, load_execution_plan
from sources.opsd.prepare import prepare_opsd
from tclean import TimeGrid

if TYPE_CHECKING:
    snakemake: Any


def main(snakemake: Any) -> None:
    """Prepare OPSD demand for the requested workflow period."""
    plan_path = getattr(snakemake.input, "plan", None)

    if plan_path is not None:
        plan = load_execution_plan(plan_path)

        batch = get_batch(plan, batch_id=snakemake.wildcards.batch_id, source="opsd")

        start = batch["start"]
        end = batch["end"]
        country_codes = batch["countries"]

    else:
        start = snakemake.params.start
        end = snakemake.params.end
        country_codes = list(snakemake.params.country_codes)

    grid = TimeGrid(start=start, end=end, frequency=snakemake.params.frequency)

    prepare_opsd(
        input_path=snakemake.input.load,
        output_path=snakemake.output.load,
        grid=grid,
        country_codes=country_codes,
    )


if __name__ == "__main__":
    sys.stderr = open(snakemake.log[0], "w", buffering=1)

    main(snakemake)
