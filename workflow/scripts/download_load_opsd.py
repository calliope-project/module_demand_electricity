"""Snakemake entry point for downloading OPSD demand data."""

import logging
import sys
from typing import TYPE_CHECKING, Any

from sources.opsd.download import download_opsd

if TYPE_CHECKING:
    snakemake: Any


def main(snakemake: Any) -> None:
    """Download the configured OPSD snapshot."""
    download_opsd(url=snakemake.params.url, output_path=snakemake.output.load)


if __name__ == "__main__":
    sys.stderr = open(snakemake.log[0], "w", buffering=1)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    main(snakemake)
