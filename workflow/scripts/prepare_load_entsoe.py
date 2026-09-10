"""Snakemake entry point for preparing ENTSO-E load data."""

from pathlib import Path
from typing import TYPE_CHECKING, Any

from _advanced_execution import get_batch, load_execution_plan
from sources.entsoe.prepare import prepare_entsoe
from tclean import TimeGrid

if TYPE_CHECKING:
    snakemake: Any


def main(snakemake: Any) -> None:
    """Prepare ENTSO-E demand for the requested workflow period."""
    plan_path = getattr(snakemake.input, "plan", None)

    if plan_path is not None:
        plan = load_execution_plan(plan_path)

        batch = get_batch(plan, batch_id=snakemake.wildcards.batch_id, source="entsoe")

        start = batch["start"]
        end = batch["end"]
        country_codes = list(batch["countries"])

    else:
        start = snakemake.params.temporal_start
        end = snakemake.params.temporal_end
        country_codes = list(snakemake.params.country_codes)

    grid = TimeGrid(start=start, end=end, frequency=snakemake.params.frequency)

    prepare_entsoe(
        input_paths=[Path(path) for path in snakemake.input.annual_files],
        output_path=snakemake.output.load,
        grid=grid,
        country_codes=country_codes,
    )


if __name__ == "__main__":
    main(snakemake)
