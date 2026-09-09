"""Shared helpers for prepared electricity-demand data."""

from pathlib import Path

import pandas as pd


def read_prepared_source(path: str | Path) -> pd.DataFrame:
    """Read a prepared source and normalise its timestamp index to UTC."""
    data = pd.read_parquet(path)

    if not isinstance(data.index, pd.DatetimeIndex):
        data.index = pd.to_datetime(data.index, utc=True)

    elif data.index.tz is None:
        data.index = data.index.tz_localize("UTC")

    else:
        data.index = data.index.tz_convert("UTC")

    data.index.name = "timestamp"

    return data
