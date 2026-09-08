"""Apply advanced T-Clean rules to basic-cleaned demand."""

from pathlib import Path

import pandas as pd
from _advanced_execution import load_execution_plan
from tclean import TimeGrid
from tclean.gap_filling import apply_advanced_rules, read_external_profile

plan = load_execution_plan(snakemake.input.plan)

grid = TimeGrid(
    start=snakemake.params.temporal_scope["start"],
    end=snakemake.params.temporal_scope["end"],
    frequency=snakemake.params.temporal_scope["frequency"],
)

data = pd.read_parquet(snakemake.input.demand)
data_source = pd.read_parquet(snakemake.input.data_source)
cleaning_method = pd.read_parquet(snakemake.input.cleaning_method)

active_rule_names = plan["active_rule_names"]

if not active_rule_names:
    print(
        "No advanced cleaning rules apply to the target contexts and period; "
        "passing basic-cleaned demand through unchanged."
    )
    filled = data.copy()

else:
    rules = pd.DataFrame(
        [
            {
                "rule_name": rule_name,
                "method": plan["rules"][rule_name]["method"],
                "source": plan["rules"][rule_name]["source"],
                "context": plan["rules"][rule_name]["context"],
                "start": plan["rules"][rule_name]["start"],
                "end": plan["rules"][rule_name]["end"],
                "scope": plan["rules"][rule_name]["scope"],
            }
            for rule_name in active_rule_names
        ]
    )

    advanced_sources = {}

    for path in snakemake.input.constructed_profiles:
        rule_name = Path(path).stem
        rule = plan["rules"][rule_name]
        source_name = rule["source"]

        profile = pd.read_parquet(path)

        if profile.shape[1] != 1:
            raise ValueError(
                f"Constructed profile for rule {rule_name!r} "
                "must contain exactly one column."
            )

        advanced_sources[source_name] = profile.iloc[:, 0]

    external_profile_paths = {
        Path(path).name: path for path in snakemake.input.external_profiles
    }

    for source_name, filename in plan["external_profile_files"].items():
        path = external_profile_paths[filename]

        advanced_sources[source_name] = read_external_profile(path, grid=grid)

    filled, _, cleaning_method = apply_advanced_rules(
        data,
        data_source,
        cleaning_method,
        rules=rules,
        advanced_sources=advanced_sources,
        grid=grid,
    )

filled.to_parquet(snakemake.output.demand)
cleaning_method.to_parquet(snakemake.output.cleaning_method)
