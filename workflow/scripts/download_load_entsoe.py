"""Snakemake entry point for downloading one ENTSO-E country-year chunk."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd
from sources.entsoe.download import download_entsoe

if TYPE_CHECKING:
    snakemake: Any


def main(snakemake: Any) -> None:
    """Download one UTC calendar year of ENTSO-E data for one country."""
    year = int(snakemake.wildcards.year)
    country_code = str(snakemake.wildcards.country)

    start = pd.Timestamp(year=year, month=1, day=1, tz="UTC")
    end = pd.Timestamp(year=year + 1, month=1, day=1, tz="UTC")

    download_entsoe(
        start=start,
        end=end,
        country_codes=[country_code],
        token_path=snakemake.input.token_entsoe,
        output_path=snakemake.output.annual_file,
        workers=1,
    )


if __name__ == "__main__":
    formatter = logging.Formatter("%(levelname)s: %(message)s")

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    log_path = Path(snakemake.log[0])
    log_path.parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(log_path, mode="w")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    logging.basicConfig(level=logging.DEBUG, handlers=[console_handler, file_handler])

    main(snakemake)
