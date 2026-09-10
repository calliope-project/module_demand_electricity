"""Prepare downloaded ENTSO-E electricity-demand data."""

from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

import pandas as pd
from tclean import TimeGrid


def _read_country_year_files(input_paths: Iterable[str | Path]) -> dict[str, pd.Series]:
    """Read and combine reusable ENTSO-E country-year files by country."""
    annual_series: dict[str, list[pd.Series]] = defaultdict(list)

    for input_path in input_paths:
        input_path = Path(input_path)
        frame = pd.read_parquet(input_path)

        if len(frame.columns) != 1:
            raise ValueError(
                "Expected each ENTSO-E country-year file to contain exactly one "
                f"country column, but {input_path} contains {list(frame.columns)}."
            )

        country_code = str(frame.columns[0])
        series = frame.iloc[:, 0].copy()
        series.name = country_code
        series.index = pd.to_datetime(series.index, utc=True)

        annual_series[country_code].append(series)

    combined: dict[str, pd.Series] = {}

    for country_code, series_parts in annual_series.items():
        series = pd.concat(series_parts).sort_index()

        duplicate_mask = series.index.duplicated(keep=False)

        if duplicate_mask.any():
            duplicate_timestamps = (
                series.index[duplicate_mask].unique().astype(str).tolist()
            )

            raise ValueError(
                f"ENTSO-E data for {country_code} contain duplicate UTC timestamps "
                f"across country-year files: {duplicate_timestamps[:10]}"
            )

        combined[country_code] = series

    return combined


def prepare_entsoe(
    *,
    input_paths: Iterable[str | Path],
    output_path: str | Path,
    grid: TimeGrid,
    country_codes: list[str],
) -> None:
    """Prepare ENTSO-E demand on the configured target grid."""
    raw_by_country = _read_country_year_files(input_paths)

    missing_countries = [
        country_code
        for country_code in country_codes
        if country_code not in raw_by_country
    ]

    if missing_countries:
        raise ValueError(
            "Missing ENTSO-E country-year inputs for configured countries: "
            f"{missing_countries}."
        )

    hourly_by_country = {
        country_code: raw_by_country[country_code].resample("1h").mean()
        for country_code in country_codes
    }

    data = pd.DataFrame(hourly_by_country)
    data = data.reindex(index=grid.target_index, columns=country_codes)
    data = data.astype(float)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data.to_parquet(output_path)
