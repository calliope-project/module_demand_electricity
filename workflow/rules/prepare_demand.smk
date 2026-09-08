rule finalise_clean_demand:
    input:
        target_plan=target_data_plan,
        demand=final_clean_demand_input,
        cleaning_method=final_cleaning_method_input,
        data_quality_failures=rules.evaluate_data_quality.output.failures,
        data_quality_issues=rules.evaluate_data_quality.output.issues,
    output:
        demand=("<resources>/automatic/{shape}/load_cleaned.parquet"),
        cleaning_method=(
            "<resources>/automatic/{shape}/load_final_cleaning_method.parquet"
        ),
        cleaning_method_rank=(
            "<resources>/automatic/{shape}/load_final_cleaning_method_rank.parquet"
        ),
    log:
        "<logs>/{shape}/finalise_clean_demand.log",
    conda:
        "../envs/module.yaml"
    params:
        source_names=active_load_sources,
        gap_filling=config["gap_filling"],
    message:
        "Finalise cleaned electricity demand and provenance."
    script:
        "../scripts/finalise_clean_demand.py"


rule demand_electricity_raster:
    input:
        demand=rules.finalise_clean_demand.output.demand,
        shapes="<shapes>",
        population="<resources>/automatic/{shape}/population_clean.tif",
    output:
        output_data="<resources>/automatic/{shape}/demand_electricity_raster.tif",
        output_profiles="<resources>/automatic/{shape}/demand_electricity_countries_profiles.parquet",
        plot_raster="<results>/{shape}/demand_electricity_raster_map.png",
        plot_profiles="<results>/{shape}/national_demand_profiles.png",
    log:
        "<logs>/{shape}/demand_electricity_raster.log",
    conda:
        "../envs/module.yaml"
    message:
        "Disaggregate annual demand to raster."
    script:
        "../scripts/demand_electricity_raster.py"


rule demand_electricity_polygon:
    input:
        demand_raster="<resources>/automatic/{shape}/demand_electricity_raster.tif",
        demand_profiles="<resources>/automatic/{shape}/demand_electricity_countries_profiles.parquet",
        cleaning_timeline="<results>/{shape}/load_cleaning_timeline.pdf",
        shapes="<shapes>",
    output:
        output_data="<output_data>",
        output_map="<results>/{shape}/demand_electricity_map.png",
    log:
        "<logs>/{shape}/demand_electricity_polygon.log",
    conda:
        "../envs/module.yaml"
    message:
        "Aggregate annual demand to shapes and scale with profile."
    script:
        "../scripts/demand_electricity_polygon.py"
