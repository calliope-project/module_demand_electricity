"""Plot electricity demand with data-quality failure annotations."""

import logging
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from _tclean_config import CONSTRUCTED_SOURCE_NAME
from cmap import Colormap
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

logger = logging.getLogger(__name__)

FIGURE_DPI = 100

PAGE_WIDTH_PX = 750
CONTEXTS_PER_PAGE = 20

PAGE_LEFT_MARGIN_PX = 68
PAGE_RIGHT_MARGIN_PX = 38
PAGE_TOP_MARGIN_PX = 72
PAGE_BOTTOM_MARGIN_PX = 42
LEGEND_HEIGHT_PX = 42

PLOT_WIDTH_PX = PAGE_WIDTH_PX - PAGE_LEFT_MARGIN_PX - PAGE_RIGHT_MARGIN_PX

BASE_ROW_HEIGHT_PX = 32
TRACE_HALF_HEIGHT_PX = 10
BOX_HALF_HEIGHT_PX = 12

MARKER_GAP_PX = 2
MARKER_LEVEL_SPACING_PX = 3

# A failure must occupy at least this much rendered horizontal space
# before an outlined interval box is useful.
BOX_MIN_WIDTH_PX = 1000


def main(
    *, demand_path: str | Path, failures_path: str | Path, output_path: str | Path
) -> None:
    """Create the electricity-demand data-quality diagnostic."""
    demand = pd.read_parquet(demand_path)
    failures = pd.read_parquet(failures_path)

    _validate_demand(demand)

    time_step = _infer_time_step(demand)
    plot_start = demand.index[0]
    plot_end = demand.index[-1] + time_step

    failures = _prepare_failures(
        failures, demand=demand, plot_start=plot_start, plot_end=plot_end
    )

    failures["display_width_px"] = (
        ((failures["end"] - failures["start"]) / time_step)
        / len(demand.index)
        * PLOT_WIDTH_PX
    )

    method_colours = _build_method_colours(failures)

    logger.info(
        "Plotting %s constructed-source data-quality failure periods "
        "across %s contexts.",
        len(failures),
        failures["context"].nunique() if not failures.empty else 0,
    )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    _write_pdf(
        demand=demand,
        failures=failures,
        method_colours=method_colours,
        plot_start=plot_start,
        plot_end=plot_end,
        output_path=output_path,
    )

    logger.info("Saved data-quality timeline to %s.", output_path)


def _validate_demand(demand: pd.DataFrame) -> None:
    """Require a plottable time-by-context demand frame."""
    if not isinstance(demand.index, pd.DatetimeIndex):
        raise ValueError("Demand must use a DatetimeIndex.")

    if len(demand.index) < 2:
        raise ValueError("At least two timestamps are required to plot data quality.")

    if demand.columns.empty:
        raise ValueError("At least one context is required to plot data quality.")

    if not demand.index.is_monotonic_increasing:
        raise ValueError("Demand timestamps must be monotonically increasing.")


def _infer_time_step(demand: pd.DataFrame) -> pd.Timedelta:
    """Infer the regular time step represented by the demand frame."""
    time_step = demand.index.to_series().diff().dropna().median()

    if pd.isna(time_step) or time_step <= pd.Timedelta(0):
        raise ValueError("Could not determine a valid temporal resolution.")

    return time_step


def _prepare_failures(
    failures: pd.DataFrame,
    *,
    demand: pd.DataFrame,
    plot_start: pd.Timestamp,
    plot_end: pd.Timestamp,
) -> pd.DataFrame:
    """Keep constructed-demand failures relevant to the plotted demand."""
    required_columns = {"context", "source", "start", "end", "method"}

    missing_columns = required_columns - set(failures.columns)

    if missing_columns:
        raise ValueError(
            "Data-quality failures are missing required columns: "
            f"{sorted(missing_columns)!r}."
        )

    selected = failures.loc[failures["source"].eq(CONSTRUCTED_SOURCE_NAME)].copy()

    if selected.empty:
        return selected.reset_index(drop=True)

    selected["start"] = pd.to_datetime(selected["start"], utc=True)
    selected["end"] = pd.to_datetime(selected["end"], utc=True)

    unknown_contexts = sorted(
        set(selected["context"].astype(str)) - set(demand.columns)
    )

    if unknown_contexts:
        raise ValueError(
            "Data-quality failures reference contexts absent from demand: "
            f"{unknown_contexts!r}."
        )

    invalid_periods = selected["end"].le(selected["start"])

    if invalid_periods.any():
        raise ValueError(
            "Data-quality failures must use positive [start, end) periods."
        )

    outside_plot = selected["start"].lt(plot_start) | selected["end"].gt(plot_end)

    if outside_plot.any():
        raise ValueError(
            "Data-quality failures extend outside the plotted demand period."
        )

    return selected.reset_index(drop=True)


def _build_method_colours(
    failures: pd.DataFrame,
) -> dict[str, tuple[float, float, float, float]]:
    """Assign one colour to each observed data-quality method."""
    if failures.empty:
        return {}

    methods = sorted(failures["method"].astype(str).unique())

    colourtheme = Colormap("bids:viridis").to_mpl()

    if len(methods) == 1:
        positions = [0.5]
    else:
        positions = np.linspace(0.08, 0.92, len(methods))

    return {
        method: colourtheme(position)
        for method, position in zip(methods, positions, strict=True)
    }


def _marker_levels(failures: pd.DataFrame) -> dict[int, int]:
    """Assign the lowest level that does not overlap another failure period."""
    if failures.empty:
        return {}

    intervals = sorted(
        (
            (failure.Index, failure.start, failure.end)
            for failure in failures.itertuples()
        ),
        key=lambda interval: (interval[1], interval[2]),
    )

    level_ends: list[pd.Timestamp] = []
    levels: dict[int, int] = {}

    for failure_index, start, end in intervals:
        for level, previous_end in enumerate(level_ends):
            # Failure periods are [start, end), so touching periods
            # do not overlap and may share the same marker level.
            if start >= previous_end:
                levels[failure_index] = level
                level_ends[level] = end
                break
        else:
            levels[failure_index] = len(level_ends)
            level_ends.append(end)

    return levels


def _build_row_layout(
    *, contexts: list[str], failures: pd.DataFrame
) -> tuple[pd.DataFrame, dict[int, int]]:
    """Allocate vertical space for traces and short failure markers."""
    rows: list[dict[str, float | str]] = []
    all_marker_levels: dict[int, int] = {}

    cursor = 0.0

    for context in contexts:
        context_failures = failures.loc[failures["context"].eq(context)]

        short_failures = context_failures.loc[
            context_failures["display_width_px"].lt(BOX_MIN_WIDTH_PX)
        ]

        marker_levels = _marker_levels(short_failures)

        all_marker_levels.update(marker_levels)

        level_count = max(marker_levels.values()) + 1 if marker_levels else 0

        marker_space = 0.0

        if level_count:
            marker_space = MARKER_GAP_PX + level_count * MARKER_LEVEL_SPACING_PX

        row_height = BASE_ROW_HEIGHT_PX + marker_space
        centre = cursor + marker_space + BASE_ROW_HEIGHT_PX / 2

        rows.append(
            {
                "context": context,
                "start": cursor,
                "centre": centre,
                "end": cursor + row_height,
            }
        )

        cursor += row_height

    layout = pd.DataFrame(rows).set_index("context")

    return layout, all_marker_levels


def _write_pdf(
    *,
    demand: pd.DataFrame,
    failures: pd.DataFrame,
    method_colours: dict[str, tuple[float, float, float, float]],
    plot_start: pd.Timestamp,
    plot_end: pd.Timestamp,
    output_path: Path,
) -> None:
    """Write one or more context pages to the data-quality PDF."""
    contexts = list(demand.columns)

    context_slices = [
        slice(start, min(start + CONTEXTS_PER_PAGE, len(contexts)))
        for start in range(0, len(contexts), CONTEXTS_PER_PAGE)
    ]

    with PdfPages(output_path) as pdf:
        for page_index, context_slice in enumerate(context_slices):
            page_contexts = contexts[context_slice]
            page_demand = demand.loc[:, page_contexts]

            page_failures = failures.loc[failures["context"].isin(page_contexts)]

            layout, marker_levels = _build_row_layout(
                contexts=page_contexts, failures=page_failures
            )

            figure, axis = _plot_page(
                demand=page_demand,
                layout=layout,
                method_colours=method_colours,
                page_index=page_index,
                page_count=len(context_slices),
                plot_start=plot_start,
                plot_end=plot_end,
            )

            _add_normalised_demand_traces(axis=axis, demand=page_demand, layout=layout)

            _add_failure_annotations(
                axis=axis,
                failures=page_failures,
                layout=layout,
                marker_levels=marker_levels,
                method_colours=method_colours,
            )

            pdf.savefig(figure)
            plt.close(figure)


def _plot_page(
    *,
    demand: pd.DataFrame,
    layout: pd.DataFrame,
    method_colours: dict[str, tuple[float, float, float, float]],
    page_index: int,
    page_count: int,
    plot_start: pd.Timestamp,
    plot_end: pd.Timestamp,
) -> tuple[plt.Figure, plt.Axes]:
    """Create one stacked-context data-quality page."""
    panel_height_px = int(np.ceil(layout["end"].iloc[-1]))

    legend_height_px = LEGEND_HEIGHT_PX

    page_height_px = (
        PAGE_TOP_MARGIN_PX + panel_height_px + legend_height_px + PAGE_BOTTOM_MARGIN_PX
    )

    figure = plt.figure(
        figsize=(PAGE_WIDTH_PX / FIGURE_DPI, page_height_px / FIGURE_DPI),
        dpi=FIGURE_DPI,
    )

    axis_bottom_px = PAGE_BOTTOM_MARGIN_PX + legend_height_px

    axis = figure.add_axes(
        [
            PAGE_LEFT_MARGIN_PX / PAGE_WIDTH_PX,
            axis_bottom_px / page_height_px,
            PLOT_WIDTH_PX / PAGE_WIDTH_PX,
            panel_height_px / page_height_px,
        ]
    )

    axis.set_xlim(plot_start, plot_end)
    axis.set_ylim(panel_height_px, 0)

    axis.set_yticks(layout["centre"].to_numpy())
    axis.set_yticklabels(demand.columns, fontsize=7)

    for boundary in layout["start"]:
        axis.axhline(boundary, linewidth=0.4, alpha=0.3, color="0.5", zorder=0)

    axis.axhline(
        layout["end"].iloc[-1], linewidth=0.4, alpha=0.3, color="0.5", zorder=0
    )

    axis.set_xlabel("Date-Time")
    axis.set_ylabel("Country")

    date_locator = mdates.AutoDateLocator(minticks=4, maxticks=8)
    axis.xaxis.set_major_locator(date_locator)
    axis.xaxis.set_major_formatter(
        mdates.ConciseDateFormatter(date_locator, show_offset=False)
    )
    axis.tick_params(axis="x", labelsize=7)

    figure.text(
        0.5,
        1.0 - (28 / page_height_px),
        "Electricity demand and data-quality failures",
        ha="center",
        va="center",
        fontsize=11,
    )

    if page_count > 1:
        figure.text(
            1.0 - (PAGE_RIGHT_MARGIN_PX / PAGE_WIDTH_PX),
            1.0 - (50 / page_height_px),
            f"Page {page_index + 1} of {page_count}",
            ha="right",
            va="center",
            fontsize=6.5,
            color="0.4",
        )

    if method_colours:
        handles = [
            Line2D(
                [0], [0], color=colour, linewidth=2.2, label=_format_method_name(method)
            )
            for method, colour in method_colours.items()
        ]

        figure.legend(
            handles=handles,
            loc="lower center",
            bbox_to_anchor=(0.5, 8 / page_height_px),
            frameon=False,
            ncol=min(3, len(handles)),
            fontsize=6.5,
            handlelength=2.0,
            columnspacing=1.0,
        )
    else:
        figure.text(
            0.5,
            8 / page_height_px,
            "No data-quality issues identified.",
            ha="center",
            va="bottom",
            fontsize=6.5,
            color="0.4",
        )

    return figure, axis


def _add_normalised_demand_traces(
    *,
    axis: plt.Axes,
    demand: pd.DataFrame,
    layout: pd.DataFrame,
    quantile: float = 0.99,
) -> None:
    """Overlay mean-normalised demand traces."""
    for context in demand.columns:
        series = demand[context].astype(float)
        centre = float(layout.loc[context, "centre"])

        mean_load = series.mean(skipna=True)

        if pd.isna(mean_load) or mean_load == 0:
            continue

        relative = (series / mean_load) - 1
        scale = relative.abs().quantile(quantile)

        if pd.isna(scale) or scale == 0:
            plotted_y = pd.Series(centre, index=series.index, dtype=float)
        else:
            scaled = relative.clip(lower=-scale, upper=scale) / scale

            plotted_y = centre - scaled * TRACE_HALF_HEIGHT_PX

        axis.plot(
            series.index, plotted_y, color="black", linewidth=0.55, alpha=0.9, zorder=3
        )


def _add_failure_annotations(
    *,
    axis: plt.Axes,
    failures: pd.DataFrame,
    layout: pd.DataFrame,
    marker_levels: dict[int, int],
    method_colours: dict[str, tuple[float, float, float, float]],
) -> None:
    """Overlay outlined periods and staggered short-period markers."""
    for failure in failures.itertuples():
        centre = float(layout.loc[failure.context, "centre"])
        colour = method_colours[str(failure.method)]

        if failure.display_width_px >= BOX_MIN_WIDTH_PX:
            start_num = mdates.date2num(failure.start)
            end_num = mdates.date2num(failure.end)

            axis.add_patch(
                Rectangle(
                    (start_num, centre - BOX_HALF_HEIGHT_PX),
                    end_num - start_num,
                    2 * BOX_HALF_HEIGHT_PX,
                    facecolor="none",
                    edgecolor=colour,
                    linewidth=1.1,
                    zorder=4,
                )
            )

            continue

        level = marker_levels[failure.Index]

        marker_y = (
            centre
            - BOX_HALF_HEIGHT_PX
            - MARKER_GAP_PX
            - level * MARKER_LEVEL_SPACING_PX
        )

        # The endpoints remain the true [start, end) period.
        # Round caps stop extremely short vector segments from
        # disappearing entirely at normal viewing scales.
        axis.plot(
            [failure.start, failure.end],
            [marker_y, marker_y],
            color=colour,
            linewidth=2.2,
            solid_capstyle="round",
            zorder=5,
        )


def _format_method_name(method: str) -> str:
    """Format a data-quality method for the legend."""
    return method.replace("_", " ").title()
