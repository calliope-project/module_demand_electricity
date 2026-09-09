"""Combine and clean one auxiliary electricity-demand group."""

from typing import TYPE_CHECKING, Any

import pandas as pd
from _advanced_execution import load_execution_plan
from _prepared_data import read_prepared_source
from tclean import TimeGrid
from tclean.gap_filling import fill_gaps

if TYPE_CHECKING:
    snakemake: Any


def main(snakemake: Any) -> None:
    """Combine and basic-clean one auxiliary source group."""
    plan = load_execution_plan(snakemake.input.plan)

    group_id = str(snakemake.wildcards.group_id)

    batch_ids = plan["groups"][group_id]

    batches_by_id = {batch["batch_id"]: batch for batch in plan["batches"]}

    batches = [batches_by_id[batch_id] for batch_id in batch_ids]

    if not batches:
        raise ValueError(f"Auxiliary group {group_id!r} contains no source batches.")

    group_starts = {
        pd.Timestamp(batch.get("group_start", batch["start"])) for batch in batches
    }

    group_ends = {
        pd.Timestamp(batch.get("group_end", batch["end"])) for batch in batches
    }

    if len(group_starts) != 1 or len(group_ends) != 1:
        raise ValueError(
            f"Auxiliary group {group_id!r} contains inconsistent logical periods."
        )

    group_start = next(iter(group_starts))
    group_end = next(iter(group_ends))

    grid = TimeGrid(
        start=group_start, end=group_end, frequency=(snakemake.params.frequency)
    )

    source_paths = list(snakemake.input.sources)

    if len(source_paths) != len(batches):
        raise ValueError(
            f"Auxiliary group {group_id!r} has "
            f"{len(batches)} planned batches but "
            f"{len(source_paths)} prepared inputs."
        )

    sources: dict[str, pd.DataFrame] = {}

    for batch, path in zip(batches, source_paths, strict=True):
        source_name = str(batch["source"])

        if source_name in sources:
            raise ValueError(
                f"Auxiliary group {group_id!r} "
                f"contains duplicate source "
                f"{source_name!r}."
            )

        sources[source_name] = read_prepared_source(path)

    contexts = sorted(
        {context for data in sources.values() for context in data.columns}
    )

    sources = {
        source_name: data.reindex(index=grid.target_index, columns=contexts)
        for source_name, data in sources.items()
    }

    basic_rules = (
        list(snakemake.params.basic_rules)
        if snakemake.params.basic_cleaning_enabled
        else []
    )

    (cleaned, data_source, cleaning_method) = fill_gaps(
        sources, grid=grid, basic_rules=basic_rules
    )

    cleaned.to_parquet(snakemake.output.demand)

    data_source.to_parquet(snakemake.output.data_source)

    cleaning_method.to_parquet(snakemake.output.cleaning_method)


if __name__ == "__main__":
    main(snakemake)
