"""Construct an auxiliary profile from cleaned source data."""

import pandas as pd
from _advanced_execution import load_execution_plan
from _tclean_config import (
    build_constructed_source_periods,
    build_scaling_source_periods,
)
from tclean import TimeGrid
from tclean.gap_filling import construct_from_sources

plan = load_execution_plan(snakemake.input.plan)

rule_name = snakemake.wildcards.rule_name
rule = plan["rules"][rule_name]

if rule["method"] != "construct_from_sources":
    raise ValueError(f"Rule {rule_name!r} is not a construct_from_sources rule.")

source_name = rule["source"]
source_definition = snakemake.params.advanced_sources[source_name]

sources = build_constructed_source_periods(source_definition)
scaling_sources = build_scaling_source_periods(source_definition)

scaling = source_definition.get("scaling")
scaling_method = None if scaling is None else scaling["method"]

grid = TimeGrid(
    start=rule["start"], end=rule["end"], frequency=snakemake.params.frequency
)

loads = [pd.read_parquet(path) for path in snakemake.input.sources]

if not loads:
    raise ValueError(f"No cleaned auxiliary data were supplied for rule {rule_name!r}.")

source_data = loads[0].copy()

for load in loads[1:]:
    source_data = source_data.combine_first(load)

source_start = source_data.index.min()
source_end = source_data.index.max() + grid.frequency

source_data = source_data.reindex(
    grid.index_for_period(start=source_start, end=source_end)
)

profile = construct_from_sources(
    source_data,
    target_index=grid.target_index,
    sources=sources,
    scaling_method=scaling_method,
    scaling_sources=scaling_sources,
    grid=grid,
)

profile.to_frame(name=rule["context"]).to_parquet(snakemake.output.profile)
