"""Rules for the ENTSO-E Power Statistics demand source."""


rule download_load_entsoe_power_statistics_year:
    output:
        annual_file=("<resources>/automatic/entsoe_power_statistics/raw/{year}.parquet"),
    log:
        "<logs>/download_load_entsoe_power_statistics_{year}.log",
    wildcard_constraints:
        year=source_year_pattern("entsoe_power_statistics"),
    localrule: True
    conda:
        "../envs/module.yaml"
    threads: 1
    resources:
        entsoe_download=1,
    message:
        ("Download ENTSO-E Power Statistics " "electricity load for {wildcards.year}.")
    script:
        "../scripts/download_load_entsoe_power_statistics.py"


rule prepare_load_entsoe_power_statistics:
    input:
        validation=("<resources>/automatic/temporal_config_validation.json"),
        target_plan=target_data_plan,
        annual_files=entsoe_power_statistics_raw_files,
    output:
        load=("<resources>/automatic/{shape}/load_entsoe_power_statistics.parquet"),
    log:
        "<logs>/{shape}/prepare_load_entsoe_power_statistics.log",
    conda:
        "../envs/module.yaml"
    params:
        temporal_start=lambda wildcards: target_source_start(
            wildcards,
            "entsoe_power_statistics",
        ),
        temporal_end=lambda wildcards: target_source_end(
            wildcards,
            "entsoe_power_statistics",
        ),
        frequency=config["temporal_scope"]["frequency"],
        country_codes=target_entsoe_power_statistics_countries,
    message:
        "Prepare electricity-demand data from ENTSO-E Power Statistics."
    script:
        "../scripts/prepare_load_entsoe_power_statistics.py"


rule prepare_auxiliary_load_entsoe_power_statistics:
    input:
        plan=auxiliary_acquisition_plan,
        annual_files=auxiliary_entsoe_power_statistics_raw_files,
    output:
        load=(
            "<resources>/automatic/{shape}/"
            "auxiliary/entsoe_power_statistics/"
            "{batch_id}.parquet"
        ),
    log:
        "<logs>/{shape}/auxiliary/entsoe_power_statistics/prepare_{batch_id}.log",
    conda:
        "../envs/module.yaml"
    params:
        frequency=config["temporal_scope"]["frequency"],
    message:
        ("Prepare auxiliary electricity-demand data " "from ENTSO-E Power Statistics.")
    script:
        "../scripts/prepare_load_entsoe_power_statistics.py"
