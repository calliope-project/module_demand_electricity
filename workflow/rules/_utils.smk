"""Collection of auxiliary functions for this module."""

from datetime import datetime, timedelta, timezone

if not isinstance(SOURCE_REGISTRY, dict):
    raise ValueError(
        "Source registry must contain a mapping " "of source identifiers to metadata."
    )


def _as_utc(value):
    """Interpret naive timestamps as UTC and convert aware timestamps to UTC. Mirrors tclean logic."""
    parsed = datetime.fromisoformat(str(value))

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def years_for_period(start, end):
    """Return UTC calendar years intersected by the half-open period [start, end). Mirrors tclean logic."""
    start = _as_utc(start)
    end = _as_utc(end)

    if end <= start:
        raise ValueError("Temporal period end must be later than its start.")

    final_included_time = end - timedelta(microseconds=1)

    return list(range(start.year, final_included_time.year + 1))


def source_year_pattern(source_name):
    """Return a year wildcard pattern for a bounded source."""
    temporal_scope = SOURCE_REGISTRY[source_name].get("temporal_scope") or {}

    start = temporal_scope.get("start")
    end = temporal_scope.get("end")

    if start is None or end is None:
        return "[0-9]{4}"

    return "|".join(str(year) for year in years_for_period(start, end))


def additional_config_validation():
    """Validate configuration relationships that require no module dependencies."""
    gap_filling = config["gap_filling"]

    if gap_filling["mode"] != "advanced":
        return

    advanced = gap_filling["advanced"]
    sources = advanced["sources"]
    advanced_entries = advanced["rules"]

    seen_entry_names = set()
    duplicate_entry_names = set()

    for advanced_entry in advanced_entries:
        entry_name = advanced_entry["name"]

        if entry_name in seen_entry_names:
            duplicate_entry_names.add(entry_name)

        seen_entry_names.add(entry_name)

    if duplicate_entry_names:
        raise ValueError(
            "Advanced_entry names must be unique. "
            f"Duplicate names: {sorted(duplicate_entry_names)}."
        )

    for advanced_entry in advanced_entries:
        source_name = advanced_entry.get("source")

        # An advanced_entry without a source explicitly leaves the target values missing.
        if source_name is None:
            continue

        if source_name not in sources:
            raise ValueError(
                f"Advanced_entry {advanced_entry['name']!r} references unknown "
                f"advanced source {source_name!r}."
            )


def validate_source_names(source_names):
    """Require configured demand sources to exist in the source registry."""
    unknown_sources = [
        source_name
        for source_name in source_names
        if source_name not in SOURCE_REGISTRY
    ]

    if unknown_sources:
        raise ValueError(
            "Unsupported electricity-demand source(s): "
            f"{unknown_sources}. "
            "Available sources are: "
            f"{sorted(SOURCE_REGISTRY)}."
        )


validate_source_names(config["load_sources"])
