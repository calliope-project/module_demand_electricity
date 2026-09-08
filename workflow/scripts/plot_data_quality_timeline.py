"""Plot electricity-demand data-quality failures."""

import logging
import sys

from _plot_data_quality_timeline import main

sys.stderr = open(snakemake.log[0], "w", buffering=1)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

main(
    demand_path=snakemake.input.demand,
    failures_path=snakemake.input.failures,
    output_path=snakemake.output.plot,
)
