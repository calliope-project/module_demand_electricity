"""Plots the diagnostic figure and writes its completeness summary."""

import logging
import sys

from _plot_timeline import main

sys.stderr = open(snakemake.log[0], "w", buffering=1)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

main(
    demand_path=snakemake.input.demand,
    basic_cleaning_method_path=snakemake.input.basic_cleaning_method,
    cleaning_method_path=snakemake.input.cleaning_method,
    cleaning_method_rank_path=snakemake.input.cleaning_method_rank,
    output_path=snakemake.output.plot,
    summary_output_path=snakemake.output.summary,
    source_names=snakemake.params.source_names,
    source_registry=snakemake.params.source_registry,
    gap_filling_config=snakemake.params.gap_filling,
)
