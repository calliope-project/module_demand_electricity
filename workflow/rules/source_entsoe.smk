"""Rules for the ENTSO-E Transparency Platform demand source."""

# Protect the user against ENTSO-E Rate limits. ENTSOE rate limits are set
# to 400calls/min. Given each download rule makes 12 API calls and resolves
# in circa 10-30seconds, we apply a conservative cap of 10 entsoe download jobs (10*12=120).
# The user may specify a different value which the conditional statement respects.
if "module_demand_electricity_entsoe_api" not in workflow.global_resources:
    workflow.register_resource(
        "module_demand_electricity_entsoe_api",
        120,
    )


rule download_load_entsoe_country_year:
    input:
        token_entsoe="<token_entsoe>",
    output:
        annual_file=("<resources>/automatic/entsoe/raw/{country}/{year}.parquet"),
    log:
        "<logs>/download_load_entsoe_{country}_{year}.log",
    wildcard_constraints:
        country="[A-Z]{3}",
        year="[0-9]{4}",
    localrule: True
    conda:
        "../envs/module.yaml"
    threads: 1
    resources:
        # Define the resource cost as the number of API calls.
        module_demand_electricity_entsoe_api=12,
    message:
        (
            "Download ENTSO-E electricity load for "
            "{wildcards.country} in {wildcards.year}."
        )
    script:
        "../scripts/download_load_entsoe.py"


rule prepare_load_entsoe:
    input:
        validation="<resources>/automatic/temporal_config_validation.json",
        target_plan=target_data_plan,
        annual_files=entsoe_raw_files,
    output:
        load="<resources>/automatic/{shape}/load_entsoe.parquet",
    log:
        "<logs>/{shape}/prepare_load_entsoe.log",
    localrule: True
    conda:
        "../envs/module.yaml"
    params:
        temporal_start=lambda wildcards: target_source_start(
            wildcards,
            "entsoe",
        ),
        temporal_end=lambda wildcards: target_source_end(
            wildcards,
            "entsoe",
        ),
        frequency=config["temporal_scope"]["frequency"],
        country_codes=target_entsoe_countries,
    message:
        "Prepare electricity load from ENTSOE."
    script:
        "../scripts/prepare_load_entsoe.py"


rule prepare_auxiliary_load_entsoe:
    input:
        plan=auxiliary_acquisition_plan,
        annual_files=auxiliary_entsoe_raw_files,
    output:
        load=("<resources>/automatic/{shape}/auxiliary/entsoe/{batch_id}.parquet"),
    log:
        "<logs>/{shape}/auxiliary/entsoe/prepare_{batch_id}.log",
    conda:
        "../envs/module.yaml"
    params:
        frequency=config["temporal_scope"]["frequency"],
    message:
        "Prepare auxiliary electricity-demand data from ENTSO-E."
    script:
        "../scripts/prepare_load_entsoe.py"
