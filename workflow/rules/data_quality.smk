"""Rules for electricity-demand data-quality evaluation."""


rule evaluate_data_quality:
    input:
        validation="<resources>/automatic/data_quality_config_validation.json",
        demand=final_clean_demand_input,
        load_inputs=configured_load_inputs,
    output:
        failures="<resources>/automatic/{shape}/load_data_quality_failures.parquet",
        issues="<resources>/automatic/{shape}/load_data_quality_issues.parquet",
    log:
        "<logs>/{shape}/evaluate_data_quality.log",
    conda:
        "../envs/module.yaml"
    params:
        source_names=active_load_sources,
        temporal_scope=config["temporal_scope"],
        data_quality=config["data_quality"],
    message:
        "Evaluate electricity-demand data quality."
    script:
        "../scripts/evaluate_data_quality.py"


rule plot_data_quality_timeline:
    input:
        demand=("<resources>/automatic/{shape}/load_cleaned.parquet"),
        failures=rules.evaluate_data_quality.output.failures,
    output:
        plot=("<results>/{shape}/" "load_data_quality_timeline.pdf"),
    log:
        "<logs>/{shape}/plot_data_quality_timeline.log",
    conda:
        "../envs/module.yaml"
    message:
        "Plot electricity-demand data-quality failures."
    script:
        "../scripts/plot_data_quality_timeline.py"
