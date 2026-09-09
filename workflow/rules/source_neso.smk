"""Rules for the NESO historic demand source."""

# Protect the user against NESO Rate limits. NESO asks for users to respect
# a 2call/min limit. We cannot implement such a limit specifically but we can
# constrain usage to 2 concurrent downloads. The user may
# specify a different value which the conditional statement respects.
if "module_demand_electricity_neso_api" not in workflow.global_resources:
    workflow.register_resource(
        "module_demand_electricity_neso_api",
        2,
    )


rule download_load_neso_year:
    output:
        annual_file=("<resources>/automatic/neso/historic_demand_{year}.csv"),
    log:
        "<logs>/download_load_neso_{year}.log",
    localrule: True
    conda:
        "../envs/module.yaml"
    threads: 1
    resources:
        module_demand_electricity_neso_api=1,
    message:
        "Download NESO historic electricity demand for {wildcards.year}."
    script:
        "../scripts/download_load_neso.py"


rule prepare_load_neso:
    input:
        validation="<resources>/automatic/temporal_config_validation.json",
        target_plan=target_data_plan,
        annual_files=neso_raw_files,
    output:
        load="<resources>/automatic/{shape}/load_neso.parquet",
    log:
        "<logs>/{shape}/prepare_load_neso.log",
    conda:
        "../envs/module.yaml"
    params:
        start=lambda wildcards: target_source_start(
            wildcards,
            "neso",
        ),
        end=lambda wildcards: target_source_end(
            wildcards,
            "neso",
        ),
        country_codes=target_neso_countries,
        frequency=config["temporal_scope"]["frequency"],
    message:
        "Prepare electricity-demand data from NESO."
    script:
        "../scripts/prepare_load_neso.py"


rule prepare_auxiliary_load_neso:
    input:
        plan=auxiliary_acquisition_plan,
        annual_files=auxiliary_neso_raw_files,
    output:
        load=("<resources>/automatic/{shape}/auxiliary/neso/{batch_id}.parquet"),
    log:
        "<logs>/{shape}/auxiliary/neso/{batch_id}.log",
    conda:
        "../envs/module.yaml"
    params:
        frequency=config["temporal_scope"]["frequency"],
    message:
        "Prepare auxiliary electricity-demand data from NESO."
    script:
        "../scripts/prepare_load_neso.py"
