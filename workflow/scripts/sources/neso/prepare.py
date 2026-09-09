"""Prepare NESO historic demand for Modelblocks."""

import logging
from collections.abc import Iterable
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = ["SETTLEMENT_DATE", "SETTLEMENT_PERIOD", "ND"]


def add_utc_timestamps(data: pd.DataFrame) -> pd.DataFrame:
    """Convert NESO settlement dates and periods to UTC timestamps."""
    prepared = data.copy()

    prepared["SETTLEMENT_DATE"] = pd.to_datetime(
        prepared["SETTLEMENT_DATE"], format="mixed", errors="raise"
    ).dt.normalize()

    prepared["SETTLEMENT_PERIOD"] = pd.to_numeric(
        prepared["SETTLEMENT_PERIOD"], errors="raise"
    ).astype(int)

    timestamp_parts: list[pd.Series] = []

    for settlement_date, day in prepared.groupby("SETTLEMENT_DATE", sort=True):
        day = day.sort_values("SETTLEMENT_PERIOD").copy()

        expected_periods = list(range(1, len(day) + 1))
        observed_periods = day["SETTLEMENT_PERIOD"].tolist()

        if observed_periods != expected_periods:
            raise ValueError(
                "NESO settlement periods are not consecutive for "
                f"{settlement_date.date()}. "
                f"Expected 1-{len(day)}."
            )

        local_start = pd.Timestamp(settlement_date, tz="Europe/London")
        local_end = local_start + pd.DateOffset(days=1)

        expected_index = pd.date_range(
            start=local_start, end=local_end, freq="30min", inclusive="left"
        )

        if len(day) != len(expected_index):
            raise ValueError(
                "NESO settlement-period count does not match the "
                "Europe/London clock for "
                f"{settlement_date.date()}: "
                f"{len(day)} records versus "
                f"{len(expected_index)} expected."
            )

        timestamp_parts.append(
            pd.Series(expected_index, index=day.index, name="timestamp")
        )

    prepared["timestamp"] = pd.concat(timestamp_parts).sort_index()

    prepared["timestamp"] = prepared["timestamp"].dt.tz_convert("UTC")

    return prepared.sort_values("timestamp")


def _read_neso_files(paths: Iterable[str | Path]) -> pd.DataFrame:
    """Read and combine annual NESO historic-demand files."""
    frames: list[pd.DataFrame] = []

    for raw_path in paths:
        path = Path(raw_path)

        logger.info("Reading NESO historic demand from %s.", path)

        try:
            frame = pd.read_csv(path, usecols=REQUIRED_COLUMNS)
        except ValueError as error:
            available_columns = pd.read_csv(path, nrows=0).columns.tolist()

            raise ValueError(
                f"NESO file {path} does not contain the required "
                f"columns {REQUIRED_COLUMNS}. "
                f"Available columns: {available_columns}"
            ) from error

        frames.append(frame)

    return pd.concat(frames, ignore_index=True)


def _prepare_half_hourly_demand(raw: pd.DataFrame) -> pd.Series:
    """Convert raw NESO records to a UTC half-hourly demand series."""
    prepared = add_utc_timestamps(raw)

    prepared["ND"] = pd.to_numeric(prepared["ND"], errors="coerce")

    invalid_demand_count = int(prepared["ND"].isna().sum())

    if invalid_demand_count:
        logger.warning(
            "NESO contains %s missing or non-numeric ND values.", invalid_demand_count
        )

    half_hourly = prepared.set_index("timestamp")["ND"].sort_index().rename("GBR")

    duplicate_mask = half_hourly.index.duplicated(keep=False)

    if duplicate_mask.any():
        duplicate_timestamps = (
            half_hourly.index[duplicate_mask].unique().astype(str).tolist()
        )

        raise ValueError(
            f"NESO data contain duplicate UTC timestamps: {duplicate_timestamps[:10]}"
        )

    return half_hourly


def _aggregate_hourly(half_hourly: pd.Series) -> pd.Series:
    """Aggregate half-hourly MW observations to hourly mean MW."""
    hourly_counts = half_hourly.resample("1h").count()

    incomplete_hours = hourly_counts.loc[hourly_counts.between(1, 1, inclusive="both")]

    if not incomplete_hours.empty:
        logger.warning(
            "NESO contains %s hours with only one valid half-hourly ND observation.",
            len(incomplete_hours),
        )

    return half_hourly.resample("1h").mean().rename("GBR")


def prepare_neso(
    *,
    input_paths: Iterable[str | Path],
    output_path: str | Path,
    target_index: pd.DatetimeIndex,
    countries: Iterable[str],
) -> None:
    """Prepare NESO demand on the requested canonical target index."""
    target_countries = list(countries)

    result = pd.DataFrame(index=target_index, columns=target_countries, dtype=float)

    if "GBR" not in target_countries:
        logger.info(
            "GBR is not part of the configured country scope. "
            "Writing an empty NESO target-grid dataframe."
        )
    else:
        raw = _read_neso_files(input_paths)
        half_hourly = _prepare_half_hourly_demand(raw)
        hourly = _aggregate_hourly(half_hourly)

        result["GBR"] = hourly.reindex(target_index)

        supplied = int(result["GBR"].notna().sum())
        missing = int(result["GBR"].isna().sum())

        logger.info(
            "Prepared NESO GBR demand: %s supplied hourly "
            "values and %s missing values.",
            supplied,
            missing,
        )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    result.to_parquet(output_path)

    logger.info(
        "Saved prepared NESO demand to %s with shape %s.", output_path, result.shape
    )
