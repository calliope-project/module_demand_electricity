"""Tests for Modelblocks-specific advanced execution metadata."""

import json

import pandas as pd
import pytest
from _advanced_execution import (
    EXECUTION_PLAN_VERSION,
    build_batch_id,
    build_group_id,
    build_source_batches,
    empty_execution_plan,
    get_batch,
    index_batch_ids_by_group,
    index_batch_ids_by_source,
    load_execution_plan,
    resolve_required_group_ids,
    serialize_batch,
)


def _requests() -> pd.DataFrame:
    start = pd.Timestamp("2020-01-01", tz="UTC")
    end = pd.Timestamp("2020-02-01", tz="UTC")
    return pd.DataFrame(
        {
            "source": ["entsoe", "entsoe", "opsd"],
            "context": ["ALB", "GRC", "ALB"],
            "start": [start, start, start],
            "end": [end, end, end],
        }
    )


def test_group_id_depends_only_on_period() -> None:
    """Test group id depends only on period."""
    start = pd.Timestamp("2020-01-01", tz="UTC")
    end = pd.Timestamp("2020-02-01", tz="UTC")
    assert build_group_id(start=start, end=end) == "20200101T0000__20200201T0000"


def test_batch_id_is_compact_and_independent_of_country_order() -> None:
    """Test batch id is compact and ignores country order."""
    start = pd.Timestamp("2020-01-01", tz="UTC")
    end = pd.Timestamp("2020-02-01", tz="UTC")

    first = build_batch_id(
        source="entsoe", start=start, end=end, countries=["ALB", "GRC"]
    )
    second = build_batch_id(
        source="entsoe", start=start, end=end, countries=["GRC", "ALB"]
    )

    assert first == second
    assert len(first) == 16
    assert set(first) <= set("0123456789abcdef")


def test_batch_id_depends_on_source() -> None:
    """Test batch id changes when the source changes."""
    start = pd.Timestamp("2020-01-01", tz="UTC")
    end = pd.Timestamp("2020-02-01", tz="UTC")

    entsoe = build_batch_id(source="entsoe", start=start, end=end, countries=["ALB"])
    opsd = build_batch_id(source="opsd", start=start, end=end, countries=["ALB"])

    assert entsoe != opsd


def test_batch_id_depends_on_period() -> None:
    """Test batch id changes when the period changes."""
    first = build_batch_id(
        source="entsoe",
        start=pd.Timestamp("2020-01-01", tz="UTC"),
        end=pd.Timestamp("2020-02-01", tz="UTC"),
        countries=["ALB"],
    )
    second = build_batch_id(
        source="entsoe",
        start=pd.Timestamp("2020-02-01", tz="UTC"),
        end=pd.Timestamp("2020-03-01", tz="UTC"),
        countries=["ALB"],
    )

    assert first != second


def test_source_batches_group_countries_by_source_and_period() -> None:
    """Test sources group countries by source and period."""
    batches = build_source_batches(_requests())
    assert len(batches) == 2
    assert batches[0]["source"] == "entsoe"
    assert batches[0]["countries"] == ["ALB", "GRC"]
    assert batches[1]["source"] == "opsd"
    assert batches[1]["countries"] == ["ALB"]
    assert batches[0]["group_id"] == batches[1]["group_id"]


def test_batch_indexes_preserve_compiled_ids() -> None:
    """Test indexes preserve ids."""
    batches = build_source_batches(_requests())
    by_source = index_batch_ids_by_source(batches)
    by_group = index_batch_ids_by_group(batches)

    assert set(by_source) == {"entsoe", "opsd"}
    assert len(by_source["entsoe"]) == 1
    assert len(by_source["opsd"]) == 1
    assert list(by_group.values())[0] == [batch["batch_id"] for batch in batches]


def test_serialize_batch_produces_json_safe_values() -> None:
    """Test for json safety."""
    batch = build_source_batches(_requests())[0]
    serialized = serialize_batch(batch)

    json.dumps(serialized)

    assert isinstance(serialized["start"], str)
    assert isinstance(serialized["end"], str)


def test_empty_execution_plan_has_stable_contract() -> None:
    """Test empty execution plan."""
    assert empty_execution_plan() == {
        "version": EXECUTION_PLAN_VERSION,
        "active_rule_names": [],
        "rules": {},
        "batches": [],
        "batch_ids_by_source": {},
        "groups": {},
        "constructed_profile_rule_names": [],
        "external_profile_files": {},
    }


def test_load_execution_plan_and_get_batch(tmp_path) -> None:
    """Test load execution plan and batch lookup."""
    batch = serialize_batch(build_source_batches(_requests())[0])

    plan = empty_execution_plan()
    plan["batches"] = [batch]

    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")

    loaded = load_execution_plan(path)
    selected = get_batch(loaded, batch_id=batch["batch_id"], source=batch["source"])

    assert selected == batch


def test_get_batch_requires_exactly_one_match() -> None:
    """Test get batch requires a single match."""
    with pytest.raises(ValueError, match="Expected exactly one auxiliary batch"):
        get_batch(empty_execution_plan(), batch_id="missing")


def test_clipped_batches_share_logical_group() -> None:
    """Check provider slices retain one logical auxiliary period."""
    group_start = pd.Timestamp("2018-01-01", tz="UTC")
    boundary = pd.Timestamp("2019-01-01", tz="UTC")
    group_end = pd.Timestamp("2021-01-01", tz="UTC")

    requests = pd.DataFrame(
        {
            "source": ["opsd", "entsoe_power_statistics"],
            "context": ["AAA", "AAA"],
            "start": [group_start, boundary],
            "end": [boundary, group_end],
            "group_start": [group_start, group_start],
            "group_end": [group_end, group_end],
        }
    )

    batches = build_source_batches(requests)

    assert len(batches) == 2

    assert batches[0]["start"] == group_start
    assert batches[0]["end"] == boundary

    assert batches[1]["start"] == boundary
    assert batches[1]["end"] == group_end

    expected_group_id = build_group_id(start=group_start, end=group_end)

    assert batches[0]["group_id"] == expected_group_id
    assert batches[1]["group_id"] == expected_group_id

    by_group = index_batch_ids_by_group(batches)

    assert list(by_group) == [expected_group_id]
    assert by_group[expected_group_id] == [batch["batch_id"] for batch in batches]

    source_periods = pd.DataFrame(
        {"context": ["AAA"], "start": [group_start], "end": [group_end]}
    )

    assert resolve_required_group_ids(batches, source_periods=source_periods) == [
        expected_group_id
    ]
