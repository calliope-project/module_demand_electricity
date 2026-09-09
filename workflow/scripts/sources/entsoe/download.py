"""Download electricity load data from ENTSO-E."""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from time import perf_counter

import pandas as pd
import pycountry
from entsoe.entsoe import EntsoePandasClient
from entsoe.exceptions import NoMatchingDataError

logger = logging.getLogger(__name__)


def load_token(filepath: str | Path) -> str:
    """Load an ENTSO-E API token from a text file."""
    return Path(filepath).read_text().strip()


def monthly_intervals(
    start: pd.Timestamp, end: pd.Timestamp
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Split a time interval at calendar-month boundaries."""
    intervals = []
    chunk_start = start

    while chunk_start < end:
        next_month = chunk_start + pd.offsets.MonthBegin(1)
        chunk_end = min(next_month, end)

        intervals.append((chunk_start, chunk_end))
        chunk_start = chunk_end

    return intervals


def download_country(
    *, country_alpha_3: str, start: pd.Timestamp, end: pd.Timestamp, token: str
) -> tuple[str, pd.Series, float]:
    """Download ENTSO-E load for one country. Accounts for ENTSO-E API P1M Constraint."""
    country = pycountry.countries.get(alpha_3=country_alpha_3)

    if country is None:
        raise ValueError(f"Unknown ISO alpha-3 country code: {country_alpha_3!r}.")

    country_alpha_2 = country.alpha_2

    client = EntsoePandasClient(api_key=token, timeout=60)

    country_start = perf_counter()

    chunks = []

    for chunk_start, chunk_end in monthly_intervals(start, end):
        logger.debug(
            "Downloading ENTSO-E load for %s/%s from %s to %s.",
            country_alpha_2,
            country_alpha_3,
            chunk_start,
            chunk_end,
        )

        try:
            chunk = client.query_load(
                country_code=country_alpha_2, start=chunk_start, end=chunk_end
            )

        except NoMatchingDataError:
            logger.debug(
                "No data found for %s/%s from %s to %s.",
                country_alpha_2,
                country_alpha_3,
                chunk_start,
                chunk_end,
            )
            continue

        chunks.append(chunk["Actual Load"])

    if chunks:
        data = pd.concat(chunks).sort_index()

        if data.index.has_duplicates:
            raise ValueError(
                f"ENTSO-E returned duplicate timestamps for {country_alpha_3!r} "
                f"between {start} and {end}."
            )

        data.name = country_alpha_3

    else:
        data = pd.Series(name=country_alpha_3, dtype=float)

    elapsed = perf_counter() - country_start

    return country_alpha_3, data, elapsed


def download_entsoe(
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
    country_codes: list[str],
    token_path: str | Path,
    output_path: str | Path,
    workers: int,
) -> None:
    """Download raw ENTSO-E load data for the requested countries."""
    token = load_token(token_path)
    output_path = Path(output_path)

    total_countries = len(country_codes)
    download_start = perf_counter()

    logger.debug(
        "Downloading ENTSO-E load for %s countries "
        "from %s to %s using %s parallel workers.",
        total_countries,
        start,
        end,
        workers,
    )

    data_by_country: dict[str, pd.Series] = {}

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                download_country,
                country_alpha_3=country_code,
                start=start,
                end=end,
                token=token,
            ): country_code
            for country_code in country_codes
        }

        for completed, future in enumerate(as_completed(futures), start=1):
            country_code = futures[future]

            try:
                (country_code, country_data, elapsed) = future.result()

            except Exception as exc:
                raise RuntimeError(
                    f"Failed to download ENTSO-E load for {country_code!r}."
                ) from exc

            data_by_country[country_code] = country_data

            logger.debug(
                "[%s/%s] Finished %s in %.1fs.",
                completed,
                total_countries,
                country_code,
                elapsed,
            )

    data = [data_by_country[country_code] for country_code in country_codes]

    raw = pd.concat(data, axis=1)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    raw.to_parquet(output_path)

    logger.debug(
        "Finished ENTSO-E downloads in %.1fs. Saved raw data to %s.",
        perf_counter() - download_start,
        output_path,
    )
