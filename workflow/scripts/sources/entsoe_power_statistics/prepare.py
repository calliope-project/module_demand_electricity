"""Prepare cached ENTSO-E Power Statistics electricity-demand data."""

from collections.abc import Iterable
from pathlib import Path

import pandas as pd
from tclean import TimeGrid


def prepare_entsoe_power_statistics(
    *,
    input_paths: Iterable[str | Path],
    output_path: str | Path,
    grid: TimeGrid,
    country_codes: list[str],
) -> None:
    """Prepare ENTSO-E Power Statistics demand on the target grid."""
    input_paths = [Path(path) for path in input_paths]

    frames = []

    for input_path in input_paths:
        frame = pd.read_parquet(input_path)

        frame.index = pd.to_datetime(frame.index, utc=True)

        frames.append(frame)

    if frames:
        data = pd.concat(frames, axis=0, sort=False).sort_index()

        duplicate_mask = data.index.duplicated(keep=False)

        if duplicate_mask.any():
            duplicate_timestamps = (
                data.index[duplicate_mask].unique().astype(str).tolist()
            )

            raise ValueError(
                "ENTSO-E Power Statistics annual files "
                "contain overlapping UTC timestamps: "
                f"{duplicate_timestamps[:10]}."
            )

    else:
        data = pd.DataFrame(dtype=float)

    data = data.reindex(index=grid.target_index, columns=country_codes)

    data = data.astype(float)

    output_path = Path(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    data.to_parquet(output_path)
