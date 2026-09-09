"""Download and harmonise annual ENTSO-E Power Statistics load data."""

import logging
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import Request, urlopen
from warnings import warn

import pandas as pd
import pycountry
from tclean import TimeGrid

logger = logging.getLogger(__name__)


URL_TEMPLATE = (
    "https://www.entsoe.eu/publications/data/power-stats/"
    "{year}/monthly_hourly_load_values_{year}.csv"
)

USER_AGENT = "modelblocks-module-demand-electricity/ENTSO-E-Power-Statistics"


def _detect_delimiter(path: Path) -> str:
    """Detect the delimiter used by an ENTSO-E Power Statistics CSV."""
    with path.open("r", encoding="utf-8-sig", errors="replace") as file:
        header = file.readline()

    if "\t" in header:
        return "\t"

    if ";" in header:
        return ";"

    raise ValueError(
        "Could not determine the delimiter used by "
        f"ENTSO-E Power Statistics file {path}."
    )


def _build_interval_start(date_short: pd.Series, time_from: pd.Series) -> pd.Series:
    """Build the hourly interval-start timestamps from source labels."""
    available = date_short.dropna()

    if available.empty:
        raise ValueError("ENTSO-E Power Statistics file contains no dates.")

    sample = str(available.iloc[0]).strip()

    if "/" in sample:
        date_format = "%d/%m/%Y"
    elif "-" in sample:
        date_format = "%d-%m-%Y"
    else:
        raise ValueError(
            f"Unsupported ENTSO-E Power Statistics date format: {sample!r}."
        )

    dates = pd.to_datetime(date_short, format=date_format, utc=True, errors="raise")

    time_strings = time_from.astype("string").str.strip()

    missing_times = time_strings.isna()

    if missing_times.any():
        raise ValueError("ENTSO-E Power Statistics contains missing TimeFrom values.")

    needs_seconds = time_strings.str.count(":") == 1

    time_strings = time_strings.where(~needs_seconds, time_strings + ":00")

    times = pd.to_timedelta(time_strings, errors="raise")

    return dates + times


def _get_map_alpha2_to_alpha3(countries_alpha_2) -> dict[str, str]:
    """Map ISO alpha-2 country codes to ISO alpha-3 codes."""
    mapping = {}

    for alpha2 in countries_alpha_2:
        country = pycountry.countries.get(alpha_2=alpha2)

        if country is not None:
            mapping[alpha2] = country.alpha_3
        else:
            warn(f"Country with alpha-2 code {alpha2!r} not found in pycountry.")

    return mapping


def harmonise_entsoe_power_statistics_csv(
    *, input_path: str | Path, output_path: str | Path, year: int
) -> None:
    """Convert one annual Power Statistics CSV to canonical Parquet."""
    input_path = Path(input_path)
    output_path = Path(output_path)

    delimiter = _detect_delimiter(input_path)

    data = pd.read_csv(
        input_path,
        sep=delimiter,
        usecols=["DateShort", "TimeFrom", "CountryCode", "Value_ScaleTo100"],
    )

    data["CountryCode"] = data["CountryCode"].astype("string").str.strip()

    data["timestamp"] = _build_interval_start(data["DateShort"], data["TimeFrom"])

    data["Value_ScaleTo100"] = pd.to_numeric(data["Value_ScaleTo100"], errors="raise")

    country_mapping = _get_map_alpha2_to_alpha3(data["CountryCode"].dropna().unique())

    data = data.loc[data["CountryCode"].isin(country_mapping)].copy()

    data["country"] = data["CountryCode"].map(country_mapping)

    duplicate_mask = data.duplicated(subset=["country", "timestamp"], keep=False)

    if duplicate_mask.any():
        examples = (
            data.loc[duplicate_mask, ["country", "timestamp", "DateShort", "TimeFrom"]]
            .drop_duplicates()
            .head(10)
            .to_dict("records")
        )

        raise ValueError(
            "ENTSO-E Power Statistics contains duplicate "
            "country/timestamp observations. "
            f"Examples: {examples}."
        )

    grid = TimeGrid(start=f"{year}-01-01", end=f"{year + 1}-01-01", frequency="1h")

    outside_year = (data["timestamp"] < grid.start) | (data["timestamp"] >= grid.end)

    if outside_year.any():
        examples = (
            data.loc[outside_year, "timestamp"]
            .drop_duplicates()
            .sort_values()
            .head(10)
            .astype(str)
            .tolist()
        )

        raise ValueError(
            f"ENTSO-E Power Statistics file for {year} "
            "contains timestamps outside its UTC calendar "
            f"year. Examples: {examples}."
        )

    wide = data.pivot(index="timestamp", columns="country", values="Value_ScaleTo100")

    wide = wide.sort_index(axis=1)

    wide = wide.reindex(index=grid.target_index)

    wide = wide.astype(float)

    wide.index.name = "timestamp"
    wide.columns.name = None

    output_path.parent.mkdir(parents=True, exist_ok=True)

    temporary_output = output_path.with_suffix(".tmp.parquet")

    try:
        wide.to_parquet(temporary_output)

        temporary_output.replace(output_path)

    finally:
        temporary_output.unlink(missing_ok=True)

    logger.info(
        "Saved ENTSO-E Power Statistics %s to %s with shape %s.",
        year,
        output_path,
        wide.shape,
    )


def download_entsoe_power_statistics_year(
    *, year: int, output_path: str | Path
) -> None:
    """Download and harmonise one annual Power Statistics file."""
    output_path = Path(output_path)

    url = URL_TEMPLATE.format(year=year)

    logger.info("Downloading ENTSO-E Power Statistics for %s.", year)

    request = Request(url, headers={"User-Agent": USER_AGENT})

    with TemporaryDirectory() as temporary_directory:
        csv_path = Path(temporary_directory) / f"monthly_hourly_load_values_{year}.csv"

        with (
            urlopen(request, timeout=300) as response,
            csv_path.open("wb") as output_file,
        ):
            shutil.copyfileobj(response, output_file)

        if csv_path.stat().st_size == 0:
            raise RuntimeError(
                f"Downloaded ENTSO-E Power Statistics file for {year} is empty."
            )

        harmonise_entsoe_power_statistics_csv(
            input_path=csv_path, output_path=output_path, year=year
        )
