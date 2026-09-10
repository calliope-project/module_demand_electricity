rule clean_demand:
    input:
        load_inputs=configured_load_inputs,
        target_plan=target_data_plan,
        validation="<resources>/automatic/gap_filling_config_validation.json",
    output:
        demand=("<resources>/automatic/{shape}/load_basic_cleaned.parquet"),
        data_source=("<resources>/automatic/{shape}/load_data_source.parquet"),
        cleaning_method=("<resources>/automatic/{shape}/load_cleaning_method.parquet"),
        cleaning_method_rank=(
            "<resources>/automatic/{shape}/load_cleaning_method_rank.parquet"
        ),
        gap_report=("<resources>/automatic/{shape}/load_gap_report.parquet"),
    log:
        "<logs>/{shape}/clean_demand.log",
    conda:
        "../envs/module.yaml"
    params:
        source_names=active_load_sources,
        temporal_scope=config["temporal_scope"],
        gap_filling=config["gap_filling"],
    message:
        "Combine and clean electricity-demand sources."
    script:
        "../scripts/clean_demand.py"


rule plot_cleaning_timeline:
    input:
        target_plan=target_data_plan,
        demand=("<resources>/automatic/{shape}/load_cleaned.parquet"),
        basic_cleaning_method=(
            "<resources>/automatic/{shape}/load_cleaning_method.parquet"
        ),
        cleaning_method=(
            "<resources>/automatic/{shape}/load_final_cleaning_method.parquet"
        ),
        cleaning_method_rank=(
            "<resources>/automatic/{shape}/load_final_cleaning_method_rank.parquet"
        ),
    output:
        plot="<results>/{shape}/load_cleaning_timeline.pdf",
        summary="<results>/{shape}/load_cleaning_summary.html",
    log:
        "<logs>/{shape}/plot_cleaning_timeline.log",
    conda:
        "../envs/module.yaml"
    params:
        source_names=active_load_sources,
        gap_filling=config["gap_filling"],
        source_registry=SOURCE_REGISTRY,
    message:
        "Plot electricity-demand cleaning provenance and summarise completeness."
    script:
        "../scripts/plot_cleaning_timeline.py"


rule clean_population:
    input:
        vector="<shapes>",
        raster=rules.unzip_population.output[0],
    output:
        path="<resources>/automatic/{shape}/population_clean.tif",
    log:
        "<logs>/{shape}/clean_population.log",
    wrapper:
        "v7.2.0/geo/rasterio/clip-geotiff"
