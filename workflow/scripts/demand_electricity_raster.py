"""Prepare electricity demand timeseries at raster resolution."""

import sys
from typing import TYPE_CHECKING, Any
from warnings import warn

import geopandas as gpd
import gregor
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rioxarray as rxr
from _plots import map_raster, plot_national_profiles
from _schemas import Shapes

if TYPE_CHECKING:
    snakemake: Any


def main(
    path_demand,
    path_population,
    path_shapes,
    start,
    end,
    path_output_data,
    path_output_profiles,
    plot_raster,
    plot_profiles,
):
    """Main function."""
    # load data
    demand = pd.read_parquet(path_demand)
    shapes = gpd.read_parquet(path_shapes)
    shapes = Shapes.validate(shapes)
    population = rxr.open_rasterio(path_population)

    # filter data
    countries = shapes.loc[shapes["shape_class"] == "land"]
    countries = countries.dissolve(by="country_id")
    population = population.sel(band=1)

    # clip population data to

    # fill NaN values in population with zeros (assuming NaN means no population)
    fill_value = population.attrs.get("_FillValue", np.nan)
    population = population.where(population != fill_value, 0)
    population.attrs["_FillValue"] = 0

    # match load data with countries
    regions = demand.columns
    missing_countries = set(regions).difference(countries.index.unique())
    if missing_countries:
        warn(f"Dropping timeseries for missing countries: {sorted(missing_countries)}")
    demand_filtered = demand.loc[:, demand.columns.isin(countries.index.unique())]

    # filter demand to time range
    demand_filtered = demand_filtered.loc[start:end]

    # drop columns with all zero or all NaN values
    all_nan = demand_filtered.isna().all(axis=0)
    all_zero = (demand_filtered == 0).all(axis=0)
    if all_nan.any():
        warn(f"Dropping columns with all NaN: {all_nan.loc[all_nan].index.tolist()}")
    if all_zero.any():
        warn(f"Dropping columns with all zero: {all_zero.loc[all_zero].index.tolist()}")
    demand_filtered = demand_filtered.loc[:, ~(all_nan | all_zero)]

    # aggregate demand over time
    demand_sum = demand_filtered.sum(axis=0).to_frame(name="demand")

    # join with countries' geometry
    demand_sum = demand_sum.join(countries["geometry"])
    demand_sum = gpd.GeoDataFrame(demand_sum, geometry="geometry")

    # disaggregate annual demand to raster resolution
    demand_raster = gregor.disaggregate.disaggregate_polygon_to_raster(
        demand_sum, column="demand", proxy=population.chunk("auto")
    )
    demand_raster.rio.to_raster(path_output_data)

    demand_filtered.to_parquet(path_output_profiles)

    map_raster(countries, demand_raster)
    plt.savefig(plot_raster, bbox_inches="tight")

    plot_national_profiles(demand_filtered)
    plt.savefig(plot_profiles, bbox_inches="tight", dpi=110)


if __name__ == "__main__":
    sys.stderr = open(snakemake.log[0], "w", buffering=1)
    main(
        path_demand=snakemake.input.demand,
        path_population=snakemake.input.population,
        path_shapes=snakemake.input.shapes,
        start=snakemake.config["temporal_scope"]["start"],
        end=snakemake.config["temporal_scope"]["end"],
        path_output_data=snakemake.output.output_data,
        path_output_profiles=snakemake.output.output_profiles,
        plot_raster=snakemake.output.plot_raster,
        plot_profiles=snakemake.output.plot_profiles,
    )
