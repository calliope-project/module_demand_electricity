"""Rules used for generic automatic resources and validation."""


rule validate_temporal_config_semantics:
    output:
        "<resources>/automatic/temporal_config_validation.json",
    log:
        "<logs>/validate_temporal_config_semantics.log",
    conda:
        "../envs/module.yaml"
    params:
        validation_kind="temporal",
        validation_config={
            "temporal_scope": config["temporal_scope"],
        },
    message:
        "Validate temporal configuration semantics."
    script:
        "../scripts/validate_config.py"


rule validate_gap_filling_config_semantics:
    output:
        "<resources>/automatic/gap_filling_config_validation.json",
    log:
        "<logs>/validate_gap_filling_config_semantics.log",
    conda:
        "../envs/module.yaml"
    params:
        validation_kind="gap_filling",
        validation_config={
            "temporal_scope": config["temporal_scope"],
            "gap_filling": config["gap_filling"],
        },
    message:
        "Validate gap-filling configuration semantics."
    script:
        "../scripts/validate_config.py"


rule validate_data_quality_config_semantics:
    output:
        "<resources>/automatic/data_quality_config_validation.json",
    log:
        "<logs>/validate_data_quality_config_semantics.log",
    conda:
        "../envs/module.yaml"
    params:
        validation_kind="data_quality",
        validation_config={
            "temporal_scope": config["temporal_scope"],
            "data_quality": config["data_quality"],
        },
    message:
        "Validate data_quality configuration semantics."
    script:
        "../scripts/validate_config.py"


checkpoint plan_target_data:
    input:
        shapes="<shapes>",
        temporal_validation=("<resources>/automatic/temporal_config_validation.json"),
    output:
        plan=("<resources>/automatic/{shape}/target_data_plan.json"),
    log:
        "<logs>/{shape}/plan_target_data.log",
    conda:
        "../envs/module.yaml"
    params:
        source_names=config["load_sources"],
        source_registry=SOURCE_REGISTRY,
        temporal_scope=config["temporal_scope"],
    message:
        "Plan target electricity-demand data acquisition."
    script:
        "../scripts/plan_target_data.py"


rule download_population:
    output:
        population=update("<resources>/automatic/population.zip"),
    log:
        "<logs>/download_population.log",
    localrule: True
    conda:
        "../envs/module.yaml"
    params:
        url=internal["resources"]["automatic"]["population"],
        expected_member=internal["resources"]["automatic"]["population_tif"],
    message:
        "Download population data."
    script:
        "../scripts/download_population.py"


rule unzip_population:
    input:
        "<resources>/automatic/population.zip",
    output:
        "<resources>/automatic/population_raw.tif",
    log:
        "<logs>/unzip.log",
    localrule: True
    params:
        internal_paths=internal["resources"]["automatic"]["population_tif"],
    message:
        "Unzip population data."
    wrapper:
        "v9.8.0/utils/libarchive/extract"
