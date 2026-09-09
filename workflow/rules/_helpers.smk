import json


def target_data_plan(wildcards):
    """Return the target-data plan after the checkpoint completes."""
    return checkpoints.plan_target_data.get(
        shape=wildcards.shape,
    ).output.plan


def read_target_data_plan(wildcards):
    """Read the resolved target-data plan for one shape."""
    plan_file = checkpoints.plan_target_data.get(
        shape=wildcards.shape,
    ).output.plan

    with open(plan_file, encoding="utf-8") as file:
        return json.load(file)


def target_source_contexts(wildcards, source_name):
    """Return target contexts assigned to one source for one shape."""
    plan = read_target_data_plan(wildcards)

    return plan["source_contexts"].get(source_name, [])


def target_source_temporal_scope(wildcards, source_name):
    """Return the planned target temporal scope for one source."""
    plan = read_target_data_plan(wildcards)

    temporal_scope = plan["source_temporal_scopes"].get(source_name)

    if temporal_scope is None:
        raise ValueError(f"Source {source_name!r} has no active target temporal scope.")

    return temporal_scope


def target_source_start(wildcards, source_name):
    """Return the planned target start timestamp for one source."""
    return target_source_temporal_scope(
        wildcards,
        source_name,
    )["start"]


def target_source_end(wildcards, source_name):
    """Return the planned target end timestamp for one source."""
    return target_source_temporal_scope(
        wildcards,
        source_name,
    )["end"]


def configured_load_inputs(wildcards):
    """Return prepared demand files for active target sources."""
    plan = read_target_data_plan(wildcards)

    return [
        ("<resources>/automatic/" f"{wildcards.shape}/" f"load_{source_name}.parquet")
        for source_name in plan["active_sources"]
    ]


def active_load_sources(wildcards):
    """Return active demand sources for one target shape."""
    plan = read_target_data_plan(wildcards)

    return plan["active_sources"]


def _read_auxiliary_plan(wildcards):
    """Read the resolved advanced execution plan for one shape."""
    plan_file = checkpoints.plan_auxiliary_data.get(
        shape=wildcards.shape,
    ).output.plan

    with open(plan_file, encoding="utf-8") as file:
        return json.load(file)


def auxiliary_acquisition_plan(wildcards):
    """Return the execution plan after the checkpoint completes."""
    return checkpoints.plan_auxiliary_data.get(
        shape=wildcards.shape,
    ).output.plan


def auxiliary_group_source_files(wildcards):
    """Return prepared source files for one auxiliary group."""
    plan = _read_auxiliary_plan(wildcards)

    batch_ids = plan["groups"][wildcards.group_id]

    batches_by_id = {batch["batch_id"]: batch for batch in plan["batches"]}

    return [
        (
            "<resources>/automatic/"
            f"{wildcards.shape}/"
            f"auxiliary/{batches_by_id[batch_id]['source']}/"
            f"{batch_id}.parquet"
        )
        for batch_id in batch_ids
    ]


def auxiliary_rule_cleaned_files(wildcards):
    """Return cleaned auxiliary files required by one advanced override."""
    plan = _read_auxiliary_plan(wildcards)

    group_ids = plan["rules"][wildcards.rule_name]["required_group_ids"]

    return [
        (
            "<resources>/automatic/"
            f"{wildcards.shape}/"
            "auxiliary/cleaned/"
            f"{group_id}.parquet"
        )
        for group_id in group_ids
    ]


def advanced_constructed_profiles(wildcards):
    """Return constructed profiles required by active advanced overrides."""
    plan = _read_auxiliary_plan(wildcards)

    return [
        (
            "<resources>/automatic/"
            f"{wildcards.shape}/"
            "auxiliary/constructed/"
            f"{rule_name}.parquet"
        )
        for rule_name in plan["constructed_profile_rule_names"]
    ]


def final_clean_demand_input(wildcards):
    """Return the cleaned demand appropriate for the configured mode."""
    if config["gap_filling"]["mode"] == "advanced":
        return (
            "<resources>/automatic/"
            f"{wildcards.shape}/"
            "load_advanced_cleaned.parquet"
        )

    return rules.clean_demand.output.demand


def final_cleaning_method_input(wildcards):
    """Return cleaning provenance appropriate for the configured mode."""
    if config["gap_filling"]["mode"] == "advanced":
        return (
            "<resources>/automatic/"
            f"{wildcards.shape}/"
            "load_advanced_cleaning_method.parquet"
        )

    return rules.clean_demand.output.cleaning_method


def advanced_external_profile_files(wildcards):
    plan = _read_auxiliary_plan(wildcards)

    return [
        f"<external_profiles>/{filename}"
        for filename in dict.fromkeys(plan["external_profile_files"].values())
    ]
