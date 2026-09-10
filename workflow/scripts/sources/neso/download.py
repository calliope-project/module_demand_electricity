"""Download annual historic electricity-demand data from NESO."""

import json
import logging
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

NESO_API_BASE = "https://api.neso.energy/api/3/action"
USER_AGENT = "modelblocks-module-demand-electricity/NESO historic demand downloader"


def _request_json(endpoint: str, parameters: dict[str, str | int]) -> dict[str, Any]:
    """Request one JSON response from the NESO CKAN API."""
    query = urlencode(parameters)
    url = f"{NESO_API_BASE}/{endpoint}?{query}"

    request = Request(url, headers={"User-Agent": USER_AGENT})

    with urlopen(request, timeout=120) as response:
        payload = json.load(response)

    if not payload.get("success", False):
        raise RuntimeError(f"NESO API request failed for {endpoint}: {payload}")

    result = payload.get("result")

    if not isinstance(result, dict):
        raise RuntimeError(f"NESO API returned an unexpected result for {endpoint}.")

    return result


def _get_historic_demand_dataset() -> dict[str, Any]:
    """Return the NESO Historic Demand Data dataset."""
    return _request_json("package_show", {"id": "historic-demand-data"})


def _select_csv_resource(dataset: dict[str, Any], *, year: int) -> dict[str, Any]:
    """Select the annual NESO historic-demand CSV resource."""
    resources = dataset.get("resources", [])

    if not isinstance(resources, list):
        raise RuntimeError("NESO Historic Demand Data has no valid resource list.")

    expected_filename = f"demanddata_{year}.csv"
    expected_title = f"historic demand data {year}"

    matching_resources: list[dict[str, Any]] = []

    for resource in resources:
        name = str(resource.get("name", "")).strip().casefold()

        url = str(resource.get("url", "")).strip()

        format_name = str(resource.get("format", "")).strip().casefold()

        url_lower = url.casefold()

        is_csv = format_name == "csv" or url_lower.endswith(".csv")

        matches_year = expected_title in name or expected_filename in url_lower

        if is_csv and matches_year and url:
            matching_resources.append(resource)

    if len(matching_resources) != 1:
        available_resources = [
            {
                "name": resource.get("name"),
                "format": resource.get("format"),
                "url": resource.get("url"),
            }
            for resource in resources
        ]

        raise RuntimeError(
            "Could not identify exactly one NESO historic-demand "
            f"CSV resource for {year}. "
            f"Matches: {len(matching_resources)}. "
            f"Resources: {available_resources}"
        )

    return matching_resources[0]


def _download_file(*, url: str, output_path: Path) -> None:
    """Download one file atomically."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = output_path.with_suffix(output_path.suffix + ".part")

    temporary_path.unlink(missing_ok=True)

    request = Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with (
            urlopen(request, timeout=300) as response,
            temporary_path.open("wb") as output_file,
        ):
            shutil.copyfileobj(response, output_file)

        if temporary_path.stat().st_size == 0:
            raise RuntimeError(f"NESO download produced an empty file: {url}")

        temporary_path.replace(output_path)

    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def download_annual_file(*, year: int, output_path: str | Path) -> None:
    """Discover and download one annual NESO historic-demand CSV."""
    output_path = Path(output_path)

    dataset = _get_historic_demand_dataset()

    logger.info("Selecting NESO historic-demand resource for %s.", year)

    resource = _select_csv_resource(dataset, year=year)

    url = str(resource["url"])

    logger.info("Downloading NESO historic demand for %s from %s.", year, url)

    _download_file(url=url, output_path=output_path)

    logger.info("Saved NESO historic demand for %s to %s.", year, output_path)
