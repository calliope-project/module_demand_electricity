"""Prepare electricity-demand data downloaded from OPSD."""

from pathlib import Path
from warnings import warn

import pandas as pd
import pycountry
from _schemas import OPSDLoad
from tclean import TimeGrid


def get_map_alpha2_to_alpha3(countries_alpha_2) -> dict[str, str]:
    """Map ISO alpha-2 country codes to alpha-3 codes."""
    mapping = {}

    for alpha2 in countries_alpha_2:
        country = pycountry.countries.get(alpha_2=alpha2)

        if country is not None:
            mapping[alpha2] = country.alpha_3
        else:
            warn(f"Country with alpha-2 code '{alpha2}' not found in pycountry.")

    return mapping


def prepare_opsd(
    *,
    input_path: str | Path,
    output_path: str | Path,
    grid: TimeGrid,
    country_codes: list[str],
) -> None:
    """Prepare OPSD demand on the requested canonical target index."""
    load = pd.read_parquet(input_path)
    load = OPSDLoad.validate(load)

    load = load.loc[load["variable"] == "load"]

    load = load.loc[load["attribute"] == "actual_entsoe_power_statistics"].copy()

    load["utc_timestamp"] = pd.to_datetime(load["utc_timestamp"], utc=True)

    # target_index is end-exclusive in conceptual terms, so
    # derive the exclusive bound from its frequency externally
    # or simply filter to timestamps represented in the index.
    load = load.loc[
        (load["utc_timestamp"] >= grid.start) & (load["utc_timestamp"] < grid.end)
    ].copy()

    country_mapping = get_map_alpha2_to_alpha3(load["region"].unique())

    load = load.loc[load["region"].isin(country_mapping)].copy()

    load.loc[:, "region"] = load["region"].map(country_mapping)

    load = load.loc[load["region"].isin(country_codes)].copy()

    load.loc[:, "data"] = pd.to_numeric(load["data"], errors="raise")

    prepared = pd.pivot(load, index="utc_timestamp", columns="region", values="data")

    prepared = prepared.reindex(index=grid.target_index, columns=country_codes)

    prepared = prepared.astype(float)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    prepared.to_parquet(output_path)
