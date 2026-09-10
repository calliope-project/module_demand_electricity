"""Snakemake entry point for downloading Orkustofnun demand data."""

import sys
from typing import TYPE_CHECKING, Any

from sources.orkustofnun.download import download_orkustofnun

if TYPE_CHECKING:
    snakemake: Any


def main(snakemake: Any) -> None:
    """Download the curated Orkustofnun demand dataset."""
    download_orkustofnun(url=snakemake.params.url, output_path=snakemake.output.load)


if __name__ == "__main__":
    sys.stderr = open(snakemake.log[0], "w", buffering=1)

    main(snakemake)
