"""Rules for the Open Power System Data demand source."""


rule download_load_opsd:
    output:
        load=update("<resources>/automatic/opsd/raw_load.parquet"),
    log:
        "<logs>/download_load_opsd.log",
    localrule: True
    conda:
        "../envs/module.yaml"
    params:
        url=internal["resources"]["automatic"]["load_opsd"],
    message:
        "Download load profiles from Open Power System Data (OPSD)."
    script:
        "../scripts/download_load_opsd.py"


rule prepare_load_opsd:
    input:
        validation="<resources>/automatic/temporal_config_validation.json",
        target_plan=target_data_plan,
        load="<resources>/automatic/opsd/raw_load.parquet",
    output:
        load="<resources>/automatic/{shape}/load_opsd.parquet",
    log:
        "<logs>/{shape}/prepare_load_opsd.log",
    conda:
        "../envs/module.yaml"
    params:
        start=lambda wildcards: target_source_start(
            wildcards,
            "opsd",
        ),
        end=lambda wildcards: target_source_end(
            wildcards,
            "opsd",
        ),
        frequency=config["temporal_scope"]["frequency"],
        country_codes=target_opsd_countries,
    message:
        "Prepare electricity-demand data from OPSD."
    script:
        "../scripts/prepare_load_opsd.py"


rule prepare_auxiliary_load_opsd:
    input:
        load=rules.download_load_opsd.output.load,
        plan=auxiliary_acquisition_plan,
    output:
        load=("<resources>/automatic/{shape}/auxiliary/opsd/{batch_id}.parquet"),
    log:
        "<logs>/{shape}/auxiliary/opsd/{batch_id}.log",
    conda:
        "../envs/module.yaml"
    params:
        frequency=config["temporal_scope"]["frequency"],
    message:
        "Prepare auxiliary electricity-demand data from OPSD."
    script:
        "../scripts/prepare_load_opsd.py"
