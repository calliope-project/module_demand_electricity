"""Snakemake entry point for annual ENTSO-E Power Statistics data."""

import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sources.entsoe_power_statistics.download import (
    download_entsoe_power_statistics_year,
)

if TYPE_CHECKING:
    snakemake: Any


def main(snakemake: Any) -> None:
    """Download and harmonise one ENTSO-E Power Statistics year."""
    download_entsoe_power_statistics_year(
        year=int(snakemake.wildcards.year),
        output_path=Path(snakemake.output.annual_file),
    )


if __name__ == "__main__":
    sys.stderr = open(snakemake.log[0], "w", buffering=1)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    main(snakemake)
