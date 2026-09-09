"""Prepare curated Orkustofnun electricity-demand data."""

from pathlib import Path

import pandas as pd
from tclean import TimeGrid

SUPPORTED_COUNTRIES = {"ISL"}


def prepare_orkustofnun(
    input_path: str | Path,
    output_path: str | Path,
    grid: TimeGrid,
    country_codes: list[str],
) -> None:
    """Prepare Orkustofnun demand on the requested time grid."""
    requested = set(country_codes)

    unsupported = requested - SUPPORTED_COUNTRIES

    if unsupported:
        raise ValueError(
            f"Orkustofnun does not provide demand data for {sorted(unsupported)}."
        )

    data = pd.read_parquet(input_path)

    required_columns = {"utc_timestamp", "ISL"}

    missing_columns = required_columns - set(data.columns)

    if missing_columns:
        raise ValueError(
            "Orkustofnun dataset is missing required columns: "
            f"{sorted(missing_columns)}."
        )

    data["utc_timestamp"] = pd.to_datetime(data["utc_timestamp"], utc=True)

    if data["utc_timestamp"].duplicated().any():
        raise ValueError("Orkustofnun dataset contains duplicate timestamps.")

    data = data.set_index("utc_timestamp")

    # Restrict to the contexts actually requested.
    data = data[list(country_codes)]

    # Align exactly to the requested T-Clean grid. Missing source
    # observations deliberately remain NaN.
    target_index = pd.DatetimeIndex(grid.target_index)

    data = data.reindex(target_index)
    data.index.name = "timestamp"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data.to_parquet(output_path)
