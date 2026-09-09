"""Download utilities for curated Orkustofnun demand data."""

from pathlib import Path

import requests


def download_orkustofnun(url: str, output_path: str | Path) -> None:
    """Download the curated Iceland electricity-demand dataset."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with requests.get(url, stream=True, timeout=120) as response:
        response.raise_for_status()

        with output_path.open("wb") as file:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    file.write(chunk)
