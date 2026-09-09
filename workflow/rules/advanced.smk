checkpoint plan_auxiliary_data:
    input:
        demand=rules.clean_demand.output.demand,
    output:
        plan=("<resources>/automatic/{shape}/auxiliary/advanced_execution_plan.json"),
    log:
        "<logs>/{shape}/auxiliary/plan_auxiliary_data.log",
    conda:
        "../envs/module.yaml"
    params:
        temporal_scope=config["temporal_scope"],
        gap_filling=config["gap_filling"],
        source_names=config["load_sources"],
        source_registry=SOURCE_REGISTRY,
    message:
        "Plan auxiliary electricity-demand acquisition."
    script:
        "../scripts/plan_auxiliary_data.py"


rule clean_auxiliary_group:
    input:
        plan=auxiliary_acquisition_plan,
        sources=auxiliary_group_source_files,
    output:
        demand=("<resources>/automatic/{shape}/auxiliary/cleaned/{group_id}.parquet"),
        data_source=(
            "<resources>/automatic/{shape}/"
            "auxiliary/cleaned/"
            "{group_id}_data_source.parquet"
        ),
        cleaning_method=(
            "<resources>/automatic/{shape}/"
            "auxiliary/cleaned/"
            "{group_id}_cleaning_method.parquet"
        ),
    log:
        "<logs>/{shape}/auxiliary/clean_{group_id}.log",
    conda:
        "../envs/module.yaml"
    params:
        frequency=config["temporal_scope"]["frequency"],
        basic_rules=config["gap_filling"]["basic"]["rules"],
        basic_cleaning_enabled=(
            config["gap_filling"]["advanced"]["auxiliary_data"]["basic_cleaning"][
                "enabled"
            ]
        ),
    message:
        "Combine and clean auxiliary electricity-demand sources."
    script:
        "../scripts/clean_auxiliary_group.py"


rule construct_auxiliary_profile:
    input:
        plan=auxiliary_acquisition_plan,
        sources=auxiliary_rule_cleaned_files,
    output:
        profile=(
            "<resources>/automatic/{shape}/"
            "auxiliary/constructed/"
            "{rule_name}.parquet"
        ),
    log:
        "<logs>/{shape}/auxiliary/construct_auxiliary_data_{rule_name}.log",
    conda:
        "../envs/module.yaml"
    params:
        frequency=config["temporal_scope"]["frequency"],
        advanced_sources=(config["gap_filling"]["advanced"]["sources"]),
    message:
        "Construct auxiliary demand profile for {wildcards.rule_name}."
    script:
        "../scripts/construct_auxiliary_profile.py"


rule apply_advanced_overrides:
    input:
        demand=rules.clean_demand.output.demand,
        data_source=rules.clean_demand.output.data_source,
        cleaning_method=rules.clean_demand.output.cleaning_method,
        plan=auxiliary_acquisition_plan,
        constructed_profiles=advanced_constructed_profiles,
        external_profiles=advanced_external_profile_files,
    output:
        demand=("<resources>/automatic/{shape}/load_advanced_cleaned.parquet"),
        cleaning_method=(
            "<resources>/automatic/{shape}/load_advanced_cleaning_method.parquet"
        ),
    log:
        "<logs>/{shape}/auxiliary/apply_advanced_overrides.log",
    conda:
        "../envs/module.yaml"
    params:
        temporal_scope=config["temporal_scope"],
    message:
        "Apply advanced electricity-demand overrides."
    script:
        "../scripts/apply_advanced_overrides.py"
