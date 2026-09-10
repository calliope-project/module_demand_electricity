"""Plot electricity demand and cleaning-method provenance through time."""

import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from _tclean_config import build_advanced_rules, build_basic_rules
from cmap import Colormap
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.colors import BoundaryNorm, ListedColormap, to_rgba
from matplotlib.patches import Rectangle

logger = logging.getLogger(__name__)

FIGURE_DPI = 100

# Layout is defined in pixels. Matplotlib requires physical figure dimensions,
# so conversion to its internal units happens only in _new_figure().
PAGE_WIDTH_PX = 750
REFERENCE_PAGE_HEIGHT_PX = 980
COUNTRIES_PER_PAGE = 35

COUNTRY_ROW_HEIGHT_PX = 20
MIN_COUNTRY_PANEL_HEIGHT_PX = 60

PAGE_LEFT_MARGIN_PX = 68
PAGE_RIGHT_MARGIN_PX = 38
PAGE_TOP_MARGIN_PX = 80
PAGE_BOTTOM_MARGIN_PX = 40
PLOT_SUMMARY_GAP_PX = 8
PANEL_LEGEND_GAP_PX = 14
X_AXIS_FOOTER_HEIGHT_PX = 48

LEGEND_FONT_SIZE = 6.5
LEGEND_SWATCH_WIDTH_PX = 15
LEGEND_SWATCH_HEIGHT_PX = 10
LEGEND_TEXT_GAP_PX = 6
LEGEND_ITEM_GAP_PX = 18
LEGEND_ROW_GAP_PX = 7
LEGEND_LINE_GAP_PX = 2
LEGEND_PADDING_TOP_PX = 8
LEGEND_PADDING_BOTTOM_PX = 8

LEGEND_PAGE_TOP_MARGIN_PX = 82
LEGEND_PAGE_BOTTOM_MARGIN_PX = 45


def main(
    *,
    demand_path: str | Path,
    basic_cleaning_method_path: str | Path,
    cleaning_method_path: str | Path,
    cleaning_method_rank_path: str | Path,
    output_path: str | Path,
    summary_output_path: str | Path,
    source_names: list[str],
    gap_filling_config: dict[str, Any],
    source_registry: Mapping[str, Mapping[str, Any]],
) -> None:
    """Create the electricity-demand cleaning diagnostic and summary."""
    demand = pd.read_parquet(demand_path)
    basic_cleaning_method = pd.read_parquet(basic_cleaning_method_path)
    cleaning_method = pd.read_parquet(cleaning_method_path)
    cleaning_method_rank = pd.read_parquet(cleaning_method_rank_path)

    _validate_alignment(
        demand=demand,
        basic_cleaning_method=basic_cleaning_method,
        cleaning_method=cleaning_method,
        cleaning_method_rank=cleaning_method_rank,
    )

    metadata = _build_cleaning_method_metadata(
        source_names=source_names,
        source_registry=source_registry,
        gap_filling_config=gap_filling_config,
    )

    _validate_cleaning_method_rank_mapping(
        cleaning_method=cleaning_method,
        cleaning_method_rank=cleaning_method_rank,
        metadata=metadata,
    )

    rank_colours = _build_rank_colours(metadata)

    background, background_cmap = _encode_rank_background(
        cleaning_method_rank=cleaning_method_rank,
        metadata=metadata,
        rank_colours=rank_colours,
    )

    summary = _build_country_summary(
        demand=demand,
        basic_cleaning_method=basic_cleaning_method,
        cleaning_method=cleaning_method,
        gap_filling_config=gap_filling_config,
    )

    legend_metadata = _filter_legend_metadata(
        metadata=metadata,
        basic_cleaning_method=basic_cleaning_method,
        cleaning_method=cleaning_method,
    )

    legend_rows = _build_legend_rows(
        metadata=legend_metadata,
        rank_colours=rank_colours,
        available_width_px=(PAGE_WIDTH_PX - PAGE_LEFT_MARGIN_PX - PAGE_RIGHT_MARGIN_PX),
    )

    logger.info(
        "Loaded %s timestamps for %s countries.", len(demand), len(demand.columns)
    )
    logger.info("Cleaning-method metadata:\n%s", metadata.to_string(index=False))

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    _write_timeline_pdf(
        demand=demand,
        background=background,
        background_cmap=background_cmap,
        summary=summary,
        legend_rows=legend_rows,
        output_path=output_path,
        gap_filling_config=gap_filling_config,
    )

    _write_summary_html(
        summary=summary,
        output_path=summary_output_path,
        gap_filling_config=gap_filling_config,
    )

    logger.info("Saved cleaning timeline to %s.", output_path)
    logger.info("Saved cleaning summary to %s.", summary_output_path)


def _new_figure(*, height_px: int) -> plt.Figure:
    """Create a figure from pixel dimensions."""
    return plt.figure(
        figsize=(PAGE_WIDTH_PX / FIGURE_DPI, height_px / FIGURE_DPI), dpi=FIGURE_DPI
    )


def _build_legend_rows(
    *,
    metadata: pd.DataFrame,
    rank_colours: dict[int, tuple[float, float, float, float]],
    available_width_px: int,
) -> list[dict[str, Any]]:
    """Measure, wrap, and pack legend entries into variable-width rows."""
    if metadata.empty:
        return []

    measurement_figure = _new_figure(height_px=200)
    measurement_figure.canvas.draw()
    renderer = measurement_figure.canvas.get_renderer()

    line_height_px = _measure_text_px(
        figure=measurement_figure, renderer=renderer, text="Ag"
    )[1]

    max_text_width_px = available_width_px - LEGEND_SWATCH_WIDTH_PX - LEGEND_TEXT_GAP_PX

    items: list[dict[str, Any]] = []

    ordered = metadata.sort_values("cleaning_method_rank")

    for row in ordered.itertuples(index=False):
        rank = int(row.cleaning_method_rank)
        lines = _wrap_legend_label(
            label=str(row.label),
            max_width_px=max_text_width_px,
            figure=measurement_figure,
            renderer=renderer,
        )

        line_widths = [
            _measure_text_px(figure=measurement_figure, renderer=renderer, text=line)[0]
            for line in lines
        ]

        text_width_px = max(line_widths, default=0.0)
        text_height_px = (
            len(lines) * line_height_px + max(0, len(lines) - 1) * LEGEND_LINE_GAP_PX
        )

        items.append(
            {
                "rank": rank,
                "colour": rank_colours[rank],
                "lines": lines,
                "width_px": (
                    LEGEND_SWATCH_WIDTH_PX + LEGEND_TEXT_GAP_PX + text_width_px
                ),
                "height_px": max(LEGEND_SWATCH_HEIGHT_PX, text_height_px),
                "line_height_px": line_height_px,
            }
        )

    plt.close(measurement_figure)

    packed_rows: list[dict[str, Any]] = []
    current_items: list[dict[str, Any]] = []
    current_width_px = 0.0
    current_height_px = 0.0

    for item in items:
        separator_px = LEGEND_ITEM_GAP_PX if current_items else 0
        proposed_width_px = current_width_px + separator_px + item["width_px"]

        if current_items and proposed_width_px > available_width_px:
            packed_rows.append({"items": current_items, "height_px": current_height_px})
            current_items = []
            current_width_px = 0.0
            current_height_px = 0.0
            separator_px = 0

        current_items.append(item)
        current_width_px += separator_px + item["width_px"]
        current_height_px = max(current_height_px, item["height_px"])

    if current_items:
        packed_rows.append({"items": current_items, "height_px": current_height_px})

    return packed_rows


def _measure_text_px(
    *, figure: plt.Figure, renderer: Any, text: str
) -> tuple[float, float]:
    """Measure one legend text line in rendered pixels."""
    artist = figure.text(0, 0, text, fontsize=LEGEND_FONT_SIZE, ha="left", va="bottom")
    bounds = artist.get_window_extent(renderer=renderer)
    artist.remove()

    return float(bounds.width), float(bounds.height)


def _wrap_legend_label(
    *, label: str, max_width_px: int, figure: plt.Figure, renderer: Any
) -> list[str]:
    """Wrap a legend label to the available rendered width."""
    words = label.split()

    if not words:
        return [""]

    lines: list[str] = []
    current = words[0]

    for word in words[1:]:
        candidate = f"{current} {word}"
        candidate_width = _measure_text_px(
            figure=figure, renderer=renderer, text=candidate
        )[0]

        if candidate_width <= max_width_px:
            current = candidate
            continue

        lines.extend(
            _split_oversized_legend_token(
                token=current,
                max_width_px=max_width_px,
                figure=figure,
                renderer=renderer,
            )
        )
        current = word

    lines.extend(
        _split_oversized_legend_token(
            token=current, max_width_px=max_width_px, figure=figure, renderer=renderer
        )
    )

    return lines


def _split_oversized_legend_token(
    *, token: str, max_width_px: int, figure: plt.Figure, renderer: Any
) -> list[str]:
    """Split an unusually long unbroken token if it cannot fit on one line."""
    if (
        _measure_text_px(figure=figure, renderer=renderer, text=token)[0]
        <= max_width_px
    ):
        return [token]

    pieces: list[str] = []
    current = ""

    for character in token:
        candidate = f"{current}{character}"
        width_px = _measure_text_px(figure=figure, renderer=renderer, text=candidate)[0]

        if current and width_px > max_width_px:
            pieces.append(current)
            current = character
        else:
            current = candidate

    if current:
        pieces.append(current)

    return pieces


def _legend_rows_height_px(rows: list[dict[str, Any]]) -> int:
    """Return total height required for a set of legend rows."""
    if not rows:
        return 0

    row_height = sum(float(row["height_px"]) for row in rows)
    gaps = LEGEND_ROW_GAP_PX * max(0, len(rows) - 1)

    return int(
        round(LEGEND_PADDING_TOP_PX + row_height + gaps + LEGEND_PADDING_BOTTOM_PX)
    )


def _take_legend_rows(
    rows: list[dict[str, Any]], *, available_height_px: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Take as many complete legend rows as fit in the available height."""
    if not rows or available_height_px <= 0:
        return [], rows

    selected: list[dict[str, Any]] = []

    for row in rows:
        candidate = [*selected, row]

        if _legend_rows_height_px(candidate) > available_height_px:
            break

        selected.append(row)

    return selected, rows[len(selected) :]


def _write_timeline_pdf(
    *,
    demand: pd.DataFrame,
    background: np.ndarray,
    background_cmap: ListedColormap,
    summary: pd.DataFrame,
    legend_rows: list[dict[str, Any]],
    output_path: Path,
    gap_filling_config: dict[str, Any],
) -> None:
    """Write a paginated timeline diagnostic to one PDF."""
    country_count = len(demand.columns)

    if country_count == 0:
        raise ValueError("At least one country is required to plot the timeline.")

    country_slices = [
        slice(start, min(start + COUNTRIES_PER_PAGE, country_count))
        for start in range(0, country_count, COUNTRIES_PER_PAGE)
    ]

    remaining_legend_rows = legend_rows

    with PdfPages(output_path) as pdf:
        for page_index, country_slice in enumerate(country_slices):
            page_demand = demand.iloc[:, country_slice]
            page_summary = summary.iloc[country_slice]
            page_background = background[country_slice, :]

            country_panel_height_px = max(
                MIN_COUNTRY_PANEL_HEIGHT_PX,
                len(page_demand.columns) * COUNTRY_ROW_HEIGHT_PX,
            )

            is_final_country_page = page_index == len(country_slices) - 1
            page_legend_rows: list[dict[str, Any]] = []

            base_height_px = (
                PAGE_TOP_MARGIN_PX
                + country_panel_height_px
                + X_AXIS_FOOTER_HEIGHT_PX
                + PAGE_BOTTOM_MARGIN_PX
            )

            if is_final_country_page and remaining_legend_rows:
                available_legend_height_px = max(
                    0, REFERENCE_PAGE_HEIGHT_PX - base_height_px - PANEL_LEGEND_GAP_PX
                )

                page_legend_rows, remaining_legend_rows = _take_legend_rows(
                    remaining_legend_rows,
                    available_height_px=available_legend_height_px,
                )

            legend_height_px = _legend_rows_height_px(page_legend_rows)

            required_height_px = base_height_px

            if page_legend_rows:
                required_height_px += PANEL_LEGEND_GAP_PX + legend_height_px

            if not is_final_country_page or remaining_legend_rows:
                page_height_px = max(required_height_px, REFERENCE_PAGE_HEIGHT_PX)
            else:
                page_height_px = required_height_px

            figure, axis, summary_axis, legend_top_px = _plot_country_page(
                demand=page_demand,
                background=page_background,
                background_cmap=background_cmap,
                page_height_px=page_height_px,
                country_panel_height_px=country_panel_height_px,
                legend_height_px=legend_height_px,
                country_start=country_slice.start + 1,
                country_end=country_slice.stop,
                country_total=country_count,
            )

            _add_normalised_demand_traces(axis=axis, demand=page_demand)

            _add_summary_panel(
                axis=summary_axis,
                summary=page_summary,
                gap_filling_config=gap_filling_config,
            )

            if page_legend_rows:
                _draw_legend_rows(
                    figure=figure, rows=page_legend_rows, top_px=legend_top_px
                )

            pdf.savefig(figure)
            plt.close(figure)

        legend_page_index = 0

        while remaining_legend_rows:
            legend_page_index += 1

            available_height_px = (
                REFERENCE_PAGE_HEIGHT_PX
                - LEGEND_PAGE_TOP_MARGIN_PX
                - LEGEND_PAGE_BOTTOM_MARGIN_PX
            )

            page_rows, new_remaining_rows = _take_legend_rows(
                remaining_legend_rows, available_height_px=available_height_px
            )

            if not page_rows:
                raise ValueError(
                    "A legend row is too tall to fit on a diagnostic PDF page."
                )

            page_rows_height_px = _legend_rows_height_px(page_rows)

            if new_remaining_rows:
                page_height_px = REFERENCE_PAGE_HEIGHT_PX
            else:
                page_height_px = (
                    LEGEND_PAGE_TOP_MARGIN_PX
                    + page_rows_height_px
                    + LEGEND_PAGE_BOTTOM_MARGIN_PX
                )

            figure = _new_figure(height_px=page_height_px)

            title = "Cleaning provenance legend"

            if legend_page_index > 1:
                title += " (continued)"

            figure.text(
                0.5,
                1.0 - (34 / page_height_px),
                title,
                ha="center",
                va="center",
                fontsize=11,
            )

            _draw_legend_rows(
                figure=figure, rows=page_rows, top_px=LEGEND_PAGE_TOP_MARGIN_PX
            )

            pdf.savefig(figure)
            plt.close(figure)

            remaining_legend_rows = new_remaining_rows


def _draw_legend_rows(
    *, figure: plt.Figure, rows: list[dict[str, Any]], top_px: int
) -> None:
    """Draw packed legend rows directly in figure coordinates."""
    figure_height_px = int(round(figure.get_figheight() * FIGURE_DPI))
    usable_width_px = PAGE_WIDTH_PX - PAGE_LEFT_MARGIN_PX - PAGE_RIGHT_MARGIN_PX

    y_px = top_px + LEGEND_PADDING_TOP_PX

    for row in rows:
        items = row["items"]
        total_width_px = sum(float(item["width_px"]) for item in items)
        total_width_px += LEGEND_ITEM_GAP_PX * max(0, len(items) - 1)

        x_px = PAGE_LEFT_MARGIN_PX + max(0.0, (usable_width_px - total_width_px) / 2)
        row_height_px = float(row["height_px"])

        for item in items:
            item_height_px = float(item["height_px"])
            item_top_px = y_px + (row_height_px - item_height_px) / 2

            swatch_top_px = item_top_px + max(
                0.0, (item_height_px - LEGEND_SWATCH_HEIGHT_PX) / 2
            )
            swatch_bottom_fraction = 1.0 - (
                (swatch_top_px + LEGEND_SWATCH_HEIGHT_PX) / figure_height_px
            )

            swatch = Rectangle(
                (x_px / PAGE_WIDTH_PX, swatch_bottom_fraction),
                LEGEND_SWATCH_WIDTH_PX / PAGE_WIDTH_PX,
                LEGEND_SWATCH_HEIGHT_PX / figure_height_px,
                transform=figure.transFigure,
                facecolor=item["colour"],
                edgecolor="0.65",
                linewidth=0.8,
            )
            figure.add_artist(swatch)

            text_x_px = x_px + LEGEND_SWATCH_WIDTH_PX + LEGEND_TEXT_GAP_PX
            text_y_px = item_top_px

            for line_index, line in enumerate(item["lines"]):
                line_top_px = text_y_px + line_index * (
                    item["line_height_px"] + LEGEND_LINE_GAP_PX
                )

                figure.text(
                    text_x_px / PAGE_WIDTH_PX,
                    1.0 - (line_top_px / figure_height_px),
                    line,
                    ha="left",
                    va="top",
                    fontsize=LEGEND_FONT_SIZE,
                )

            x_px += item["width_px"] + LEGEND_ITEM_GAP_PX

        y_px += row_height_px + LEGEND_ROW_GAP_PX


def _validate_alignment(
    *,
    demand: pd.DataFrame,
    basic_cleaning_method: pd.DataFrame,
    cleaning_method: pd.DataFrame,
    cleaning_method_rank: pd.DataFrame,
) -> None:
    """Require all diagnostic inputs to use the same time-country grid."""
    for name, frame in {
        "basic_cleaning_method": basic_cleaning_method,
        "cleaning_method": cleaning_method,
        "cleaning_method_rank": cleaning_method_rank,
    }.items():
        if not frame.index.equals(demand.index):
            raise ValueError(f"{name} does not use the same time index as demand.")

        if not frame.columns.equals(demand.columns):
            raise ValueError(f"{name} does not use the same country columns as demand.")


def _validate_cleaning_method_rank_mapping(
    *,
    cleaning_method: pd.DataFrame,
    cleaning_method_rank: pd.DataFrame,
    metadata: pd.DataFrame,
) -> None:
    """Require provenance strings and numeric codes to describe the same methods."""
    method_to_rank = (
        metadata.set_index("cleaning_method")["cleaning_method_rank"]
        .astype(int)
        .to_dict()
    )

    methods = {
        str(value)
        for value in pd.unique(cleaning_method.to_numpy().ravel())
        if pd.notna(value)
    }

    unknown_methods = sorted(methods - set(method_to_rank))

    if unknown_methods:
        raise ValueError(
            "Cleaning provenance contains methods absent from plotting "
            f"metadata: {unknown_methods!r}."
        )

    expected = cleaning_method.apply(lambda column: column.map(method_to_rank))

    actual = cleaning_method_rank.apply(pd.to_numeric, errors="coerce")

    mismatch = expected.ne(actual) & ~(expected.isna() & actual.isna())

    if not mismatch.any().any():
        return

    row_index, column_index = np.argwhere(mismatch.to_numpy())[0]

    timestamp = cleaning_method.index[row_index]
    country = cleaning_method.columns[column_index]
    method = cleaning_method.iloc[row_index, column_index]
    expected_rank = expected.iloc[row_index, column_index]
    actual_rank = actual.iloc[row_index, column_index]

    raise ValueError(
        "Cleaning-method rank is inconsistent with cleaning provenance "
        f"at {timestamp!r}, country {country!r}: "
        f"method {method!r} expects code {expected_rank}, "
        f"but rank data contains {actual_rank}."
    )


def _build_rank_colours(
    metadata: pd.DataFrame,
) -> dict[int, tuple[float, float, float, float]]:
    """Assign colours by provenance category."""
    colours: dict[int, tuple[float, float, float, float]] = {}

    ordered = metadata.sort_values("cleaning_method_rank")

    observed = ordered.loc[ordered["category"] == "observed"]
    imputed = ordered.loc[ordered["category"] == "imputed"]
    missing = ordered.loc[ordered["category"] == "missing"]

    # Primary source is white. Subsequent observed sources
    # become gradually darker, but remain very light so that
    # the black demand trace stays clearly visible.
    observed_shades = np.linspace(1.0, 0.60, len(observed))

    for (_, row), shade in zip(observed.iterrows(), observed_shades, strict=True):
        rank = int(row["cleaning_method_rank"])
        colours[rank] = (float(shade), float(shade), float(shade), 1.0)

    if not imputed.empty:
        colourtheme = Colormap("bids:viridis").to_mpl()
        positions = np.linspace(0.05, 0.95, len(imputed))

        for (_, row), position in zip(imputed.iterrows(), positions, strict=True):
            rank = int(row["cleaning_method_rank"])
            colours[rank] = colourtheme(position)

    for _, row in missing.iterrows():
        rank = int(row["cleaning_method_rank"])
        colours[rank] = to_rgba("#ff0000")

    expected_ranks = set(metadata["cleaning_method_rank"].astype(int))
    missing_colours = expected_ranks - set(colours)

    if missing_colours:
        raise ValueError(f"No colour was assigned to ranks: {sorted(missing_colours)}")

    return colours


def _encode_rank_background(
    *,
    cleaning_method_rank: pd.DataFrame,
    metadata: pd.DataFrame,
    rank_colours: dict[int, tuple[float, float, float, float]],
) -> tuple[np.ndarray, ListedColormap]:
    """Encode ranks as contiguous plotting codes."""
    rank_order = metadata["cleaning_method_rank"].astype(int).tolist()
    rank_to_code = {rank: code for code, rank in enumerate(rank_order)}

    encoded = cleaning_method_rank.apply(lambda column: column.map(rank_to_code))
    colour_list = [rank_colours[rank] for rank in rank_order]

    # Input frames are time × country, whereas imshow expects
    # country × time for this figure orientation.
    background = encoded.to_numpy(dtype=int).T

    return (background, ListedColormap(colour_list))


def _plot_country_page(
    *,
    demand: pd.DataFrame,
    background: np.ndarray,
    background_cmap: ListedColormap,
    page_height_px: int,
    country_panel_height_px: int,
    legend_height_px: int,
    country_start: int,
    country_end: int,
    country_total: int,
) -> tuple[plt.Figure, plt.Axes, plt.Axes, int]:
    """Plot one country page and return the top position available for a legend."""
    country_count = len(demand.columns)

    if len(demand.index) < 2:
        raise ValueError(
            "At least two timestamps are required to plot the cleaning timeline."
        )

    time_step = demand.index.to_series().diff().dropna().median()

    if pd.isna(time_step) or time_step <= pd.Timedelta(0):
        raise ValueError("Could not determine a valid temporal resolution.")

    start = demand.index[0]
    end = demand.index[-1] + time_step

    figure = _new_figure(height_px=page_height_px)

    usable_width_px = PAGE_WIDTH_PX - PAGE_LEFT_MARGIN_PX - PAGE_RIGHT_MARGIN_PX
    content_width_px = usable_width_px - PLOT_SUMMARY_GAP_PX

    timeline_width_px = content_width_px * (3.9 / (3.9 + 2.5))
    summary_width_px = content_width_px - timeline_width_px

    axis_bottom_px = page_height_px - PAGE_TOP_MARGIN_PX - country_panel_height_px

    axis = figure.add_axes(
        [
            PAGE_LEFT_MARGIN_PX / PAGE_WIDTH_PX,
            axis_bottom_px / page_height_px,
            timeline_width_px / PAGE_WIDTH_PX,
            country_panel_height_px / page_height_px,
        ]
    )

    summary_axis = figure.add_axes(
        [
            (PAGE_LEFT_MARGIN_PX + timeline_width_px + PLOT_SUMMARY_GAP_PX)
            / PAGE_WIDTH_PX,
            axis_bottom_px / page_height_px,
            summary_width_px / PAGE_WIDTH_PX,
            country_panel_height_px / page_height_px,
        ],
        sharey=axis,
    )

    background_norm = BoundaryNorm(
        np.arange(-0.5, background_cmap.N + 0.5, 1), background_cmap.N
    )

    axis.imshow(
        background,
        aspect="auto",
        interpolation="nearest",
        cmap=background_cmap,
        norm=background_norm,
        extent=(
            mdates.date2num(start),
            mdates.date2num(end),
            country_count - 0.5,
            -0.5,
        ),
        rasterized=True,
        zorder=0,
    )

    row_centres = np.arange(country_count)

    axis.set_yticks(row_centres)
    axis.set_yticklabels(demand.columns, fontsize=7)

    axis.set_xlim(start, end)
    axis.set_ylim(country_count - 0.5, -0.5)

    # Light boundaries make individual country strips clear
    # without obscuring the provenance colours.
    row_boundaries = np.arange(-0.5, country_count, 1)

    axis.set_yticks(row_boundaries, minor=True)
    axis.grid(axis="y", which="minor", linewidth=0.4, alpha=0.35)
    axis.tick_params(axis="y", which="minor", left=False)

    axis.set_xlabel("Date-Time")
    axis.set_ylabel("Country")

    date_locator = mdates.AutoDateLocator(minticks=4, maxticks=8)

    axis.xaxis.set_major_locator(date_locator)
    axis.xaxis.set_major_formatter(
        mdates.ConciseDateFormatter(date_locator, show_offset=False)
    )
    axis.tick_params(axis="x", labelsize=7)

    summary_axis.set_xlim(0, 1)
    summary_axis.tick_params(
        axis="both",
        which="both",
        left=False,
        bottom=False,
        labelleft=False,
        labelbottom=False,
    )

    for spine in summary_axis.spines.values():
        spine.set_visible(False)

    for boundary in row_boundaries:
        summary_axis.axhline(boundary, linewidth=0.4, alpha=0.35, color="0.5", zorder=0)

    summary_axis.axvline(0.0, linewidth=0.6, color="0.7")

    figure.text(
        0.5,
        1.0 - (34 / page_height_px),
        "Electricity demand and cleaning provenance",
        ha="center",
        va="center",
        fontsize=11,
    )

    if country_total > COUNTRIES_PER_PAGE:
        figure.text(
            1.0 - (PAGE_RIGHT_MARGIN_PX / PAGE_WIDTH_PX),
            1.0 - (62 / page_height_px),
            f"Countries {country_start}–{country_end} of {country_total}",
            ha="right",
            va="center",
            fontsize=6.5,
            color="0.4",
        )

    legend_top_px = (
        PAGE_TOP_MARGIN_PX
        + country_panel_height_px
        + X_AXIS_FOOTER_HEIGHT_PX
        + PANEL_LEGEND_GAP_PX
    )

    if legend_height_px == 0:
        legend_top_px = page_height_px - PAGE_BOTTOM_MARGIN_PX

    return figure, axis, summary_axis, legend_top_px


def _add_normalised_demand_traces(
    *,
    axis: plt.Axes,
    demand: pd.DataFrame,
    half_height: float = 0.35,
    quantile: float = 0.99,
) -> None:
    """Overlay mean-normalised demand traces."""
    for row_index, country in enumerate(demand.columns):
        series = demand[country].astype(float)

        mean_load = series.mean(skipna=True)

        if pd.isna(mean_load) or mean_load == 0:
            continue

        relative = (series / mean_load) - 1
        scale = relative.abs().quantile(quantile)

        if pd.isna(scale) or scale == 0:
            plotted_y = pd.Series(row_index, index=series.index, dtype=float)
        else:
            scaled = relative.clip(lower=-scale, upper=scale) / scale

            # The y-axis is inverted, so subtracting makes
            # above-average demand appear visually upward.
            plotted_y = row_index - scaled * half_height

        axis.plot(
            series.index, plotted_y, color="black", linewidth=0.55, alpha=0.9, zorder=3
        )


def _build_country_summary(
    *,
    demand: pd.DataFrame,
    basic_cleaning_method: pd.DataFrame,
    cleaning_method: pd.DataFrame,
    gap_filling_config: dict[str, Any],
) -> pd.DataFrame:
    """Summarise load and completion at each cleaning stage."""
    summary = pd.DataFrame(index=demand.columns)

    summary.index.name = "country"

    summary["mean_load_gw"] = demand.mean(axis=0, skipna=True) / 1000

    raw_present = basic_cleaning_method.apply(
        lambda column: column.str.startswith("observed_", na=False)
    )

    basic_present = basic_cleaning_method.notna() & basic_cleaning_method.ne("missing")

    final_present = cleaning_method.notna() & cleaning_method.ne("missing")

    summary["raw_completion"] = raw_present.mean(axis=0)

    mode = gap_filling_config["mode"]

    if mode in {"basic", "advanced"}:
        summary["basic_completion"] = basic_present.mean(axis=0)

    if mode == "advanced":
        summary["advanced_completion"] = final_present.mean(axis=0)

    summary["final_complete"] = final_present.all(axis=0)

    return summary


def _add_summary_panel(
    *, axis: plt.Axes, summary: pd.DataFrame, gap_filling_config: dict[str, Any]
) -> None:
    """Add paper-friendly completeness columns beside the timeline."""
    columns: list[tuple[str, str, str]] = [
        ("Mean\n(GW)", "mean_load_gw", "mean"),
        ("Raw\n(%)", "raw_completion", "completion"),
    ]

    mode = gap_filling_config["mode"]

    if mode in {"basic", "advanced"}:
        columns.append(("Basic\n(%)", "basic_completion", "completion"))

    if mode == "advanced":
        columns.append(("Advanced\n(%)", "advanced_completion", "completion"))

    columns.append(("Status", "final_complete", "status"))

    x_positions = np.linspace(0.08, 0.92, len(columns))

    for x_position, (header, _, _) in zip(x_positions, columns, strict=True):
        axis.text(
            x_position,
            1.01,
            header,
            transform=axis.transAxes,
            ha="center",
            va="bottom",
            fontsize=7,
            fontweight="bold",
        )

    for row_index, (_, row) in enumerate(summary.iterrows()):
        for x_position, (_, field, kind) in zip(x_positions, columns, strict=True):
            if kind == "mean":
                value = row[field]

                label = "—" if pd.isna(value) else f"{float(value):.1f}"

                axis.text(
                    x_position, row_index, label, ha="center", va="center", fontsize=7
                )

            elif kind == "completion":
                axis.text(
                    x_position,
                    row_index,
                    _format_completion(row[field]),
                    ha="center",
                    va="center",
                    fontsize=7,
                )

            else:
                complete = bool(row[field])

                axis.text(
                    x_position,
                    row_index,
                    "✓" if complete else "✗",
                    ha="center",
                    va="center",
                    fontsize=9,
                    fontweight="bold",
                    color=("#2e7d32" if complete else "#c62828"),
                )


def _format_completion(value: float) -> str:
    """Format completion without ever rounding incomplete data to 100.0."""
    if pd.isna(value):
        return "—"

    value = float(value)

    if value >= 1.0:
        return "100.0"

    percentage = np.floor(value * 1000) / 10
    percentage = min(percentage, 99.9)

    return f"{percentage:.1f}"


def _write_summary_html(
    *,
    summary: pd.DataFrame,
    output_path: str | Path,
    gap_filling_config: dict[str, Any],
) -> None:
    """Write a standalone, human-readable HTML completeness table."""
    table = pd.DataFrame(
        {
            "Country": summary.index,
            "Mean load (GW)": [
                "—" if pd.isna(value) else f"{float(value):.1f}"
                for value in summary["mean_load_gw"]
            ],
            "Raw completion": [
                f"{_format_completion(value)}%" for value in summary["raw_completion"]
            ],
        }
    )

    mode = gap_filling_config["mode"]

    if mode in {"basic", "advanced"}:
        table["Basic completion"] = [
            f"{_format_completion(value)}%" for value in summary["basic_completion"]
        ]

    if mode == "advanced":
        table["Advanced completion"] = [
            f"{_format_completion(value)}%" for value in summary["advanced_completion"]
        ]

    table["Status"] = [
        (
            '<span class="complete">✓ Complete</span>'
            if bool(complete)
            else '<span class="incomplete">✗ Incomplete</span>'
        )
        for complete in summary["final_complete"]
    ]

    output_path = Path(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    table_html = table.to_html(
        index=False, border=0, escape=False, classes="summary-table"
    )

    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Electricity-demand cleaning summary</title>
<style>
body {{
    font-family: Arial, sans-serif;
    margin: 2rem;
    color: #222;
}}
h1 {{
    font-size: 1.35rem;
}}
.summary-table {{
    border-collapse: collapse;
    font-size: 0.95rem;
}}
.summary-table th,
.summary-table td {{
    border-bottom: 1px solid #ddd;
    padding: 0.45rem 0.75rem;
    text-align: right;
}}
.summary-table th:first-child,
.summary-table td:first-child {{
    text-align: left;
}}
.complete {{
    color: #2e7d32;
    font-weight: bold;
}}
.incomplete {{
    color: #c62828;
    font-weight: bold;
}}
.note {{
    max-width: 60rem;
    font-size: 0.9rem;
    color: #555;
}}
</style>
</head>
<body>
<h1>Electricity-demand cleaning summary</h1>
<p class="note">
Completion is measured against all expected periods on the configured time grid.
Incomplete percentages are floored to one decimal place, so an incomplete series
can never be displayed as 100.0%.
</p>
{table_html}
</body>
</html>
"""

    output_path.write_text(document, encoding="utf-8")


def _build_cleaning_method_metadata(
    *,
    source_names: list[str],
    gap_filling_config: dict[str, Any],
    source_registry: Mapping[str, Mapping[str, Any]],
) -> pd.DataFrame:
    """Build cleaning-method metadata in configured order."""
    rows: list[dict[str, Any]] = []
    rank = 0

    for source_name in source_names:
        rows.append(
            {
                "cleaning_method": f"observed_{source_name}",
                "cleaning_method_rank": rank,
                "label": (
                    f"[Src.] {_format_source_name(source_name, source_registry)}"
                ),
                "category": "observed",
            }
        )

        rank += 1

    basic_rules = build_basic_rules(gap_filling_config)

    for rule in basic_rules:
        rule_name = rule["name"]

        rows.append(
            {
                "cleaning_method": rule_name,
                "cleaning_method_rank": rank,
                "label": f"[Bsc.] {_format_rule_name(rule_name)}",
                "category": "imputed",
            }
        )

        rank += 1

    advanced_rules = build_advanced_rules(gap_filling_config)

    if not advanced_rules.empty:
        for rule_name in advanced_rules["rule_name"]:
            rows.append(
                {
                    "cleaning_method": rule_name,
                    "cleaning_method_rank": rank,
                    "label": f"[Adv.] {_format_rule_name(rule_name)}",
                    "category": "imputed",
                }
            )

            rank += 1

    rows.append(
        {
            "cleaning_method": "missing",
            "cleaning_method_rank": rank,
            "label": "[Missing]",
            "category": "missing",
        }
    )

    return pd.DataFrame(rows)


def _filter_legend_metadata(
    *,
    metadata: pd.DataFrame,
    basic_cleaning_method: pd.DataFrame,
    cleaning_method: pd.DataFrame,
) -> pd.DataFrame:
    """Keep only cleaning methods represented in this workflow result."""
    used_methods: set[str] = set()

    for frame in (basic_cleaning_method, cleaning_method):
        values = pd.unique(frame.to_numpy().ravel())

        used_methods.update(str(value) for value in values if pd.notna(value))

    # Keep missing in the legend as the fixed diagnostic reference colour,
    # even when this particular result is complete.
    used_methods.add("missing")

    return metadata.loc[metadata["cleaning_method"].isin(used_methods)].copy()


def _format_source_name(
    source_name: str, source_registry: Mapping[str, Mapping[str, Any]]
) -> str:
    """Return the configured human-readable source name."""
    metadata = source_registry.get(source_name, {})

    return str(metadata.get("display_name", source_name))


def _format_rule_name(name: str) -> str:
    """Format one configured rule name for display."""
    return name.replace("_", " ").capitalize()
