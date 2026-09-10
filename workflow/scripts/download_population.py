"""Download and cache the population-data archive."""

import logging
import shutil
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from zipfile import BadZipFile, ZipFile, is_zipfile

logger = logging.getLogger(__name__)

USER_AGENT = "modelblocks-module-demand-electricity/population downloader"


def _is_valid_cached_archive(path: Path, *, expected_member: str) -> bool:
    """Return whether an existing population archive is suitable for reuse."""
    if not path.exists() or path.stat().st_size == 0:
        return False

    if not is_zipfile(path):
        return False

    try:
        with ZipFile(path) as archive:
            members = {name.replace("\\", "/") for name in archive.namelist()}
    except (OSError, BadZipFile):
        return False

    expected_member = expected_member.replace("\\", "/")

    return expected_member in members


def download_population(
    *, url: str, output_path: str | Path, expected_member: str
) -> None:
    """Download the population archive unless a valid cached copy exists."""
    output_path = Path(output_path)

    if _is_valid_cached_archive(output_path, expected_member=expected_member):
        logger.info("Using cached population archive: %s", output_path)
        return

    if output_path.exists():
        logger.warning(
            "Cached population archive is invalid; downloading a replacement."
        )
        output_path.unlink()

    output_path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = output_path.with_suffix(output_path.suffix + ".part")
    temporary_path.unlink(missing_ok=True)

    logger.info("Downloading population archive from %s.", url)

    request = Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with (
            urlopen(request, timeout=300) as response,
            temporary_path.open("wb") as output_file,
        ):
            content_length = response.headers.get("Content-Length")
            shutil.copyfileobj(response, output_file)

        downloaded_size = temporary_path.stat().st_size

        if content_length is not None and downloaded_size != int(content_length):
            raise RuntimeError(
                "Population download is incomplete: "
                f"received {downloaded_size} of {content_length} bytes."
            )

        if not _is_valid_cached_archive(
            temporary_path, expected_member=expected_member
        ):
            raise RuntimeError(
                "Downloaded population archive does not contain "
                f"the expected file {expected_member!r}."
            )

        temporary_path.replace(output_path)

    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

    logger.info(
        "Saved population archive to %s (%s bytes).",
        output_path,
        output_path.stat().st_size,
    )


if __name__ == "__main__":
    sys.stderr = open(snakemake.log[0], "w", buffering=1)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    download_population(
        url=snakemake.params.url,
        output_path=snakemake.output.population,
        expected_member=snakemake.params.expected_member,
    )
