"""Download and cache the fixed OPSD electricity-demand snapshot."""

import logging
import shutil
from pathlib import Path
from urllib.request import Request, urlopen

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

logger = logging.getLogger(__name__)

USER_AGENT = "modelblocks-module-demand-electricity/OPSD downloader"

REQUIRED_COLUMNS = {"utc_timestamp", "region", "variable", "attribute", "data"}


def _is_valid_cached_snapshot(path: Path) -> bool:
    """Return whether an existing OPSD Parquet snapshot is suitable for reuse."""
    if not path.exists() or path.stat().st_size == 0:
        return False

    try:
        columns = set(pq.read_schema(path).names)
    except (OSError, pa.ArrowInvalid):
        return False

    return REQUIRED_COLUMNS.issubset(columns)


def _convert_csv_to_parquet(csv_path: Path, parquet_path: Path) -> None:
    """Convert an OPSD CSV snapshot to Parquet without loading it fully into memory."""
    reader = pacsv.open_csv(csv_path)

    if not REQUIRED_COLUMNS.issubset(reader.schema.names):
        raise RuntimeError(
            "Downloaded OPSD snapshot does not contain the expected CSV structure."
        )

    with pq.ParquetWriter(parquet_path, reader.schema, compression="zstd") as writer:
        for batch in reader:
            writer.write_batch(batch)


def download_opsd(*, url: str, output_path: str | Path) -> None:
    """Download the OPSD snapshot unless a valid cached copy exists."""
    output_path = Path(output_path)

    if _is_valid_cached_snapshot(output_path):
        logger.info("Using cached OPSD snapshot: %s", output_path)
        return

    if output_path.exists():
        logger.warning("Cached OPSD snapshot is invalid; downloading a replacement.")
        output_path.unlink()

    output_path.parent.mkdir(parents=True, exist_ok=True)

    temporary_csv_path = output_path.with_suffix(".csv.part")
    temporary_parquet_path = output_path.with_suffix(output_path.suffix + ".part")

    temporary_csv_path.unlink(missing_ok=True)
    temporary_parquet_path.unlink(missing_ok=True)

    logger.info("Downloading OPSD snapshot from %s.", url)

    request = Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with (
            urlopen(request, timeout=300) as response,
            temporary_csv_path.open("wb") as output_file,
        ):
            content_length = response.headers.get("Content-Length")

            shutil.copyfileobj(response, output_file)

        downloaded_size = temporary_csv_path.stat().st_size

        if content_length is not None and downloaded_size != int(content_length):
            raise RuntimeError(
                "OPSD download is incomplete: "
                f"received {downloaded_size} "
                f"of {content_length} bytes."
            )

        _convert_csv_to_parquet(temporary_csv_path, temporary_parquet_path)

        if not _is_valid_cached_snapshot(temporary_parquet_path):
            raise RuntimeError(
                "Converted OPSD snapshot does not contain "
                "the expected Parquet structure."
            )

        temporary_parquet_path.replace(output_path)
        temporary_csv_path.unlink()

    except Exception:
        temporary_csv_path.unlink(missing_ok=True)
        temporary_parquet_path.unlink(missing_ok=True)
        raise

    logger.info(
        "Saved OPSD snapshot to %s (%s bytes).", output_path, output_path.stat().st_size
    )
