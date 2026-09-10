"""Snakemake entry point for downloading NESO historic demand."""

import logging
import sys
from typing import TYPE_CHECKING, Any

from sources.neso.download import download_annual_file

if TYPE_CHECKING:
    snakemake: Any


def main(snakemake: Any) -> None:
    """Download one annual NESO historic-demand file."""
    download_annual_file(
        year=int(snakemake.wildcards.year), output_path=snakemake.output.annual_file
    )


if __name__ == "__main__":
    sys.stderr = open(snakemake.log[0], "w", buffering=1)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    main(snakemake)
