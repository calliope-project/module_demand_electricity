"""Rules for Icelandic electricity demand from Orkustofnun."""


rule download_load_orkustofnun:
    output:
        load=update("<resources>/automatic/orkustofnun/raw_load.parquet"),
    log:
        "<logs>/download_load_orkustofnun.log",
    localrule: True
    conda:
        "../envs/module.yaml"
    params:
        url=internal["resources"]["automatic"]["load_orkustofnun"],
    message:
        "Download curated Icelandic electricity-demand data from Orkustofnun."
    script:
        "../scripts/download_load_orkustofnun.py"


rule prepare_load_orkustofnun:
    input:
        validation="<resources>/automatic/temporal_config_validation.json",
        target_plan=target_data_plan,
        load="<resources>/automatic/orkustofnun/raw_load.parquet",
    output:
        load=("<resources>/automatic/{shape}/load_orkustofnun.parquet"),
    log:
        "<logs>/{shape}/prepare_load_orkustofnun.log",
    conda:
        "../envs/module.yaml"
    params:
        start=lambda wildcards: target_source_start(
            wildcards,
            "orkustofnun",
        ),
        end=lambda wildcards: target_source_end(
            wildcards,
            "orkustofnun",
        ),
        frequency=config["temporal_scope"]["frequency"],
        country_codes=lambda wildcards: target_source_contexts(
            wildcards,
            "orkustofnun",
        ),
    message:
        "Prepare electricity-demand data from Orkustofnun."
    script:
        "../scripts/prepare_load_orkustofnun.py"


rule prepare_auxiliary_load_orkustofnun:
    input:
        load=rules.download_load_orkustofnun.output.load,
        plan=auxiliary_acquisition_plan,
    output:
        load=("<resources>/automatic/{shape}/auxiliary/orkustofnun/{batch_id}.parquet"),
    log:
        "<logs>/{shape}/auxiliary/orkustofnun/{batch_id}.log",
    conda:
        "../envs/module.yaml"
    params:
        frequency=config["temporal_scope"]["frequency"],
    message:
        "Prepare auxiliary electricity-demand data from Orkustofnun."
    script:
        "../scripts/prepare_load_orkustofnun.py"
