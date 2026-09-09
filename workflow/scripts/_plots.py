"""A collection of plotting functions shared across scripts."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.dates import DateFormatter

MW_to_GW = 1e-3
GW_to_TW = 1e-3
MW_to_TW = 1e-6


WhiteToRed = LinearSegmentedColormap.from_list("WhiteToRed", ["#ffffff", "#ff0000"])


def plot_national_profiles(df: pd.DataFrame):
    """Plot electricity demand profiles for all countries."""
    color_missing = "#ff9393"
    color_zero = "#dea1fd"
    profiles_GW = df * MW_to_GW
    profiles_GW_d = profiles_GW.resample("1D").mean()

    n_profiles = df.shape[1]

    fig, axs = plt.subplots(1, n_profiles, figsize=(17, 6))
    axs = np.atleast_1d(axs).ravel()
    fig.subplots_adjust(wspace=0)

    for ax, column in zip(axs, profiles_GW.columns):
        val_max = profiles_GW[column].max()
        val_max = val_max if val_max > 0 else 1

        ax.plot(
            profiles_GW[column], profiles_GW.index, label=column, color="C0", alpha=0.3
        )
        ax.plot(
            profiles_GW_d[column],
            profiles_GW_d.index,
            label=f"{column} (daily mean)",
            color="k",
            linewidth=1,
        )

        # plot missing values as red
        highlight_values(
            ax, profiles_GW[column], lambda x: x.isna(), color=color_missing, alpha=1
        )
        # plot zero values as violet
        highlight_values(
            ax, profiles_GW[column], lambda x: x == 0, color=color_zero, alpha=1
        )
        ax.invert_yaxis()
        ax.set_xlim(0, val_max * 1.1)
        ax.set_xticks([0, np.round(val_max, 1)])
        ax.set_xticklabels(["", np.round(val_max, 1)])
        ax.title.set_text(column)

    for ax in axs[1:]:
        ax.set_yticks([])

    axs[0].set_ylabel("Time")
    axs[0].yaxis.set_major_formatter(DateFormatter("%Y-%m-%d"))
    axs[0].set_xlabel("Electricity load (GW)")

    fig.suptitle("National electricity load for ENTSO-E countries")

    # legend below the plot
    handles = {
        plt.Line2D([0], [0], color="C0", alpha=0.3, label="Hourly load"),
        plt.Line2D([0], [0], color="k", label="Daily mean load"),
        plt.Rectangle((0, 0), 1, 1, color=color_zero, alpha=1, label="Zero values"),
        plt.Rectangle(
            (0, 0), 1, 1, color=color_missing, alpha=1, label="Missing values"
        ),
    }
    labels = [h.get_label() for h in handles]
    fig.legend(handles=handles, labels=labels, loc="lower center", ncol=4)

    return fig


def highlight_values(ax, series, condition, color="red", alpha=0.5):
    """Highlight values in a plot based on a condition."""
    mask = condition(series)

    # if all values are True, color all
    if mask.all():
        ax.axhspan(series.index[0], series.index[-1], color=color, alpha=alpha)
        return

    begins = series.index[mask & ~mask.shift(1, fill_value=False)]
    ends = series.index[mask & ~mask.shift(-1, fill_value=False)]
    for begin, end in zip(begins, ends):
        ax.axhspan(begin, end, color=color, alpha=alpha)


def map_raster(shapes, demand):
    """Plot annual electricity demand on a map."""
    fig, ax = plt.subplots(figsize=(7, 6), dpi=300)

    demand_coarse = demand.coarsen(x=5, y=5, boundary="trim").sum()

    demand_coarse = demand_coarse.rio.write_crs(demand.rio.crs)
    demand_coarse = demand_coarse.rio.write_transform(demand.rio.transform())

    demand_coarse.plot(ax=ax, cmap=WhiteToRed, vmin=0, vmax=10000, aspect=None)

    shapes.boundary.plot(ax=ax, color="white", alpha=0.3, linewidth=0.5, aspect=None)

    return fig


def map_polygon(demand):
    """Plot annual electricity demand on a map."""
    summed_demand = demand["sum"].sum() * MW_to_TW

    fig, ax = plt.subplots(figsize=(7, 6))
    demand.plot(ax=ax, column="sum", cmap=WhiteToRed, legend=True, aspect=None)
    demand.geometry.boundary.plot(
        ax=ax, color="white", alpha=0.3, linewidth=0.5, aspect=None
    )
    demand.geometry.boundary.plot(
        ax=ax, color="k", alpha=0.3, linewidth=0.3, aspect=None
    )

    ax.set_title(f"Total annual electricity demand:\n{summed_demand:.0f} TWh")

    return fig
