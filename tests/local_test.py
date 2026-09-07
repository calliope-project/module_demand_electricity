"""Tests to be executed locally, as they are more computationally intense."""

import subprocess
from pathlib import Path

LOCAL_TEST_PATH = Path(__file__).parent / "local"


def test_europe_end_to_end(
    europe_large_shapes: Path,
    token_entsoe: Path,
):
    """Run a full European end-to-end electricity-demand test."""
    subprocess.run(
        ["snakemake", "--use-conda", "--cores", "8", "--forceall"],
        check=True,
        cwd=LOCAL_TEST_PATH,
    )
