"""Generate the final cleaned demand and provenance outputs."""

import shutil

import pandas as pd
from _tclean_config import build_advanced_rules, build_basic_rules
from tclean.gap_filling import build_cleaning_method_ranks, derive_cleaning_method_rank

shutil.copyfile(snakemake.input.demand, snakemake.output.demand)

cleaning_method = pd.read_parquet(snakemake.input.cleaning_method)

gap_filling = snakemake.params.gap_filling

basic_rules = build_basic_rules(gap_filling)
advanced_rules = build_advanced_rules(gap_filling)

basic_rule_names = [rule["name"] for rule in basic_rules]

advanced_rule_names = (
    advanced_rules["rule_name"].tolist() if not advanced_rules.empty else []
)

ranks = build_cleaning_method_ranks(
    snakemake.params.source_names,
    basic_rule_names=basic_rule_names,
    advanced_rule_names=advanced_rule_names,
)

cleaning_method_rank = derive_cleaning_method_rank(
    cleaning_method=cleaning_method, ranks=ranks
)

cleaning_method.to_parquet(snakemake.output.cleaning_method)

cleaning_method_rank.to_parquet(snakemake.output.cleaning_method_rank)
