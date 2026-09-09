"""Source specific helpers snakemake rules."""

# ENTSOE POWER STATISTICS


def entsoe_power_statistics_annual_files(years):
    """Return annual ENTSO-E Power Statistics files."""
    return [
        ("<resources>/automatic/entsoe_power_statistics/raw/" f"{int(year)}.parquet")
        for year in years
    ]


def entsoe_power_statistics_raw_files(wildcards):
    """Return Power Statistics annual files required by the target period."""
    years = years_for_period(
        target_source_start(
            wildcards,
            "entsoe_power_statistics",
        ),
        target_source_end(
            wildcards,
            "entsoe_power_statistics",
        ),
    )

    return entsoe_power_statistics_annual_files(years)


def auxiliary_entsoe_power_statistics_raw_files(wildcards):
    """Return Power Statistics annual files required by one auxiliary batch."""
    plan = _read_auxiliary_plan(wildcards)

    batch = next(
        batch
        for batch in plan["batches"]
        if (
            batch["batch_id"] == wildcards.batch_id
            and batch["source"] == "entsoe_power_statistics"
        )
    )

    return entsoe_power_statistics_annual_files(batch["years"])


def target_entsoe_power_statistics_countries(wildcards):
    """Return Power Statistics target countries for one shape."""
    return target_source_contexts(
        wildcards,
        "entsoe_power_statistics",
    )


# ENTSOE


def entsoe_annual_files(countries, years):
    """Return reusable ENTSO-E country-year raw-file paths."""
    return [
        "<resources>/automatic/entsoe/raw/" f"{country}/{int(year)}.parquet"
        for country in countries
        for year in years
    ]


def entsoe_raw_files(wildcards):
    """Return ENTSO-E country-year files required for one target shape."""
    plan = read_target_data_plan(wildcards)

    countries = plan["source_contexts"].get("entsoe", [])

    years = years_for_period(
        target_source_start(
            wildcards,
            "entsoe",
        ),
        target_source_end(
            wildcards,
            "entsoe",
        ),
    )

    return entsoe_annual_files(countries, years)


def target_entsoe_countries(wildcards):
    """Return ENTSO-E target countries for one shape."""
    return target_source_contexts(wildcards, "entsoe")


def auxiliary_entsoe_raw_files(wildcards):
    """Return ENTSO-E country-year files required by one auxiliary batch."""
    plan = _read_auxiliary_plan(wildcards)

    batch = next(
        batch
        for batch in plan["batches"]
        if (batch["batch_id"] == wildcards.batch_id and batch["source"] == "entsoe")
    )

    return entsoe_annual_files(batch["countries"], batch["years"])


# NESO


def neso_annual_files(years):
    """Return reusable annual NESO raw-file paths for the requested years."""
    return [
        "<resources>/automatic/neso/" f"historic_demand_{int(year)}.csv"
        for year in years
    ]


def neso_raw_files(wildcards):
    """Return annual NESO input files for the planned target period."""
    years = years_for_period(
        target_source_start(
            wildcards,
            "neso",
        ),
        target_source_end(
            wildcards,
            "neso",
        ),
    )

    return neso_annual_files(years)


def auxiliary_neso_raw_files(wildcards):
    """Return annual NESO files required by one auxiliary batch."""
    plan = _read_auxiliary_plan(wildcards)

    batch = next(
        batch
        for batch in plan["batches"]
        if (batch["batch_id"] == wildcards.batch_id and batch["source"] == "neso")
    )

    return neso_annual_files(batch["years"])


def target_neso_countries(wildcards):
    """Return NESO target countries for one shape."""
    return target_source_contexts(
        wildcards,
        "neso",
    )


# OPSD


def target_opsd_countries(wildcards):
    """Return OPSD target countries for one shape."""
    return target_source_contexts(
        wildcards,
        "opsd",
    )
