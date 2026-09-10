"""Tests for target electricity-demand acquisition planning."""

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

# workflow/scripts is not a Python package, so expose it for direct imports.
ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "workflow" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

from plan_target_data import (  # noqa: E402
    TARGET_DATA_PLAN_VERSION,
    _as_utc,
    build_target_data_plan,
    effective_source_temporal_scope,
    supported_target_contexts,
    uncovered_temporal_intervals,
    write_target_data_plan,
)

# ---------------------------------------------------------------------------
# Timestamp handling
# ---------------------------------------------------------------------------


def test_as_utc_localises_naive_timestamp():
    """Naive timestamps are interpreted as UTC."""
    result = _as_utc("2020-01-01")

    assert result == pd.Timestamp("2020-01-01T00:00:00Z")


def test_as_utc_converts_aware_timestamp():
    """Timezone-aware timestamps are converted to UTC."""
    result = _as_utc("2020-01-01T01:00:00+01:00")

    assert result == pd.Timestamp("2020-01-01T00:00:00Z")


# ---------------------------------------------------------------------------
# Source temporal-scope intersection
# ---------------------------------------------------------------------------


def test_effective_scope_uses_full_requested_period_without_source_bounds():
    """An unbounded source inherits the complete requested period."""
    result = effective_source_temporal_scope({}, start="2018-01-01", end="2021-01-01")

    assert result == {
        "start": "2018-01-01T00:00:00+00:00",
        "end": "2021-01-01T00:00:00+00:00",
    }


def test_effective_scope_clips_source_end():
    """A source end bound clips the requested period."""
    metadata = {"temporal_scope": {"start": "2005-01-01", "end": "2019-01-01"}}

    result = effective_source_temporal_scope(
        metadata, start="2018-01-01", end="2021-01-01"
    )

    assert result == {
        "start": "2018-01-01T00:00:00+00:00",
        "end": "2019-01-01T00:00:00+00:00",
    }


def test_effective_scope_clips_source_start():
    """A source start bound clips the requested period."""
    metadata = {"temporal_scope": {"start": "2019-01-01", "end": "2026-01-01"}}

    result = effective_source_temporal_scope(
        metadata, start="2018-01-01", end="2021-01-01"
    )

    assert result == {
        "start": "2019-01-01T00:00:00+00:00",
        "end": "2021-01-01T00:00:00+00:00",
    }


@pytest.mark.parametrize(
    ("source_start", "source_end"),
    [("2000-01-01", "2018-01-01"), ("2021-01-01", "2025-01-01")],
)
def test_effective_scope_returns_none_without_overlap(source_start, source_end):
    """Sources touching but not overlapping the request are inactive."""
    metadata = {"temporal_scope": {"start": source_start, "end": source_end}}

    result = effective_source_temporal_scope(
        metadata, start="2018-01-01", end="2021-01-01"
    )

    assert result is None


# ---------------------------------------------------------------------------
# Geographic support
# ---------------------------------------------------------------------------


def test_supported_contexts_respects_source_contexts():
    """Only explicitly supported target contexts are returned."""
    result = supported_target_contexts(
        ["AAA", "BBB", "CCC"], metadata={"contexts": ["AAA", "CCC", "DDD"]}
    )

    assert result == ["AAA", "CCC"]


@pytest.mark.parametrize("metadata", [{}, {"contexts": None}, {"contexts": []}])
def test_missing_or_empty_contexts_means_no_geographic_restriction(metadata):
    """Missing or empty source contexts allow all target contexts."""
    result = supported_target_contexts(["AAA", "BBB"], metadata=metadata)

    assert result == ["AAA", "BBB"]


# ---------------------------------------------------------------------------
# Temporal coverage helper
# ---------------------------------------------------------------------------


def test_uncovered_intervals_returns_full_period_without_sources():
    """No source intervals means the complete request is uncovered."""
    gaps = uncovered_temporal_intervals([], start="2018-01-01", end="2021-01-01")

    assert gaps == [
        (pd.Timestamp("2018-01-01T00:00:00Z"), pd.Timestamp("2021-01-01T00:00:00Z"))
    ]


def test_uncovered_intervals_accepts_adjacent_half_open_intervals():
    """Adjacent half-open source intervals provide continuous coverage."""
    gaps = uncovered_temporal_intervals(
        [("2018-01-01", "2019-01-01"), ("2019-01-01", "2021-01-01")],
        start="2018-01-01",
        end="2021-01-01",
    )

    assert gaps == []


def test_uncovered_intervals_merges_overlapping_intervals():
    """Overlapping source intervals jointly provide continuous coverage."""
    gaps = uncovered_temporal_intervals(
        [("2018-01-01", "2020-01-01"), ("2019-01-01", "2021-01-01")],
        start="2018-01-01",
        end="2021-01-01",
    )

    assert gaps == []


def test_uncovered_intervals_reports_internal_gap():
    """An uncovered interval between two sources is reported exactly."""
    gaps = uncovered_temporal_intervals(
        [("2018-01-01", "2019-01-01"), ("2019-02-01", "2021-01-01")],
        start="2018-01-01",
        end="2021-01-01",
    )

    assert gaps == [
        (pd.Timestamp("2019-01-01T00:00:00Z"), pd.Timestamp("2019-02-01T00:00:00Z"))
    ]


# ---------------------------------------------------------------------------
# Complete target plans
# ---------------------------------------------------------------------------


def test_target_plan_clips_source_temporal_scopes():
    """The plan records the effective interval for every active source."""
    source_registry = {
        "old_source": {
            "temporal_scope": {"start": "2005-01-01", "end": "2019-01-01"},
            "contexts": ["AAA"],
        },
        "new_source": {
            "temporal_scope": {"start": "2019-01-01", "end": "2026-01-01"},
            "contexts": ["AAA"],
        },
    }

    plan = build_target_data_plan(
        target_contexts=["AAA"],
        source_names=["old_source", "new_source"],
        source_registry=source_registry,
        temporal_scope={"start": "2018-01-01", "end": "2021-01-01"},
    )

    assert plan["version"] == TARGET_DATA_PLAN_VERSION

    assert plan["source_temporal_scopes"] == {
        "old_source": {
            "start": "2018-01-01T00:00:00+00:00",
            "end": "2019-01-01T00:00:00+00:00",
        },
        "new_source": {
            "start": "2019-01-01T00:00:00+00:00",
            "end": "2021-01-01T00:00:00+00:00",
        },
    }


def test_target_plan_accepts_contiguous_source_coverage():
    """Adjacent source intervals can jointly cover a target context."""
    source_registry = {
        "source_a": {
            "temporal_scope": {"start": "2005-01-01", "end": "2019-01-01"},
            "contexts": ["AAA"],
        },
        "source_b": {
            "temporal_scope": {"start": "2019-01-01", "end": "2026-01-01"},
            "contexts": ["AAA"],
        },
    }

    plan = build_target_data_plan(
        target_contexts=["AAA"],
        source_names=["source_a", "source_b"],
        source_registry=source_registry,
        temporal_scope={"start": "2018-01-01", "end": "2021-01-01"},
    )

    assert plan["active_sources"] == ["source_a", "source_b"]

    assert plan["source_contexts"] == {"source_a": ["AAA"], "source_b": ["AAA"]}


def test_target_plan_rejects_temporal_coverage_gap():
    """Reject a target context with a gap between source periods."""
    source_registry = {
        "source_a": {
            "temporal_scope": {"start": "2005-01-01", "end": "2019-01-01"},
            "contexts": ["AAA"],
        },
        "source_b": {
            "temporal_scope": {"start": "2019-02-01", "end": "2026-01-01"},
            "contexts": ["AAA"],
        },
    }

    with pytest.raises(ValueError, match=r"2019-01-01T00:00:00\+00:00") as exc_info:
        build_target_data_plan(
            target_contexts=["AAA"],
            source_names=["source_a", "source_b"],
            source_registry=source_registry,
            temporal_scope={"start": "2018-01-01", "end": "2021-01-01"},
        )

    message = str(exc_info.value)

    assert "AAA" in message
    assert "2019-01-01T00:00:00+00:00" in message
    assert "2019-02-01T00:00:00+00:00" in message


def test_target_plan_rejects_completely_unsupported_context():
    """A target context with no usable source is rejected."""
    source_registry = {"source_a": {"contexts": ["AAA"]}}

    with pytest.raises(ValueError, match="BBB") as exc_info:
        build_target_data_plan(
            target_contexts=["AAA", "BBB"],
            source_names=["source_a"],
            source_registry=source_registry,
            temporal_scope={"start": "2018-01-01", "end": "2021-01-01"},
        )

    message = str(exc_info.value)

    assert "BBB" in message
    assert "2018-01-01T00:00:00+00:00" in message
    assert "2021-01-01T00:00:00+00:00" in message


def test_target_plan_checks_coverage_per_context():
    """Temporal coverage must be complete independently for each context."""
    source_registry = {
        "old_source": {
            "temporal_scope": {"start": "2010-01-01", "end": "2019-01-01"},
            "contexts": ["AAA", "BBB"],
        },
        "new_source": {
            "temporal_scope": {"start": "2019-01-01", "end": "2025-01-01"},
            "contexts": ["AAA"],
        },
    }

    with pytest.raises(ValueError, match="BBB") as exc_info:
        build_target_data_plan(
            target_contexts=["AAA", "BBB"],
            source_names=["old_source", "new_source"],
            source_registry=source_registry,
            temporal_scope={"start": "2018-01-01", "end": "2021-01-01"},
        )

    message = str(exc_info.value)

    # AAA is completely covered by old_source + new_source.
    # BBB loses coverage at the old_source boundary.
    assert "BBB" in message
    assert "2019-01-01T00:00:00+00:00" in message
    assert "2021-01-01T00:00:00+00:00" in message


def test_target_plan_excludes_temporally_inactive_source():
    """A source outside the requested interval remains in the plan but inactive."""
    source_registry = {
        "inactive_source": {
            "temporal_scope": {"start": "2000-01-01", "end": "2018-01-01"},
            "contexts": ["AAA"],
        },
        "active_source": {
            "temporal_scope": {"start": "2018-01-01", "end": "2025-01-01"},
            "contexts": ["AAA"],
        },
    }

    plan = build_target_data_plan(
        target_contexts=["AAA"],
        source_names=["inactive_source", "active_source"],
        source_registry=source_registry,
        temporal_scope={"start": "2018-01-01", "end": "2021-01-01"},
    )

    assert plan["active_sources"] == ["active_source"]

    assert plan["source_contexts"]["inactive_source"] == []

    assert plan["source_temporal_scopes"]["inactive_source"] is None


def test_target_plan_preserves_configured_source_priority():
    """Active sources retain the order supplied in configuration."""
    source_registry = {
        "source_a": {"contexts": ["AAA"]},
        "source_b": {"contexts": ["AAA"]},
        "source_c": {"contexts": ["AAA"]},
    }

    plan = build_target_data_plan(
        target_contexts=["AAA"],
        source_names=["source_c", "source_a", "source_b"],
        source_registry=source_registry,
        temporal_scope={"start": "2018-01-01", "end": "2021-01-01"},
    )

    assert plan["active_sources"] == ["source_c", "source_a", "source_b"]


def test_target_plan_sorts_and_deduplicates_target_contexts():
    """Target contexts are stored uniquely and deterministically."""
    source_registry = {"source_a": {}}

    plan = build_target_data_plan(
        target_contexts=["CCC", "AAA", "BBB", "AAA"],
        source_names=["source_a"],
        source_registry=source_registry,
        temporal_scope={"start": "2018-01-01", "end": "2021-01-01"},
    )

    assert plan["target_contexts"] == ["AAA", "BBB", "CCC"]

    assert plan["source_contexts"]["source_a"] == ["AAA", "BBB", "CCC"]


def test_target_plan_rejects_unknown_source():
    """Configured sources must exist in the source registry."""
    with pytest.raises(ValueError, match="Unsupported electricity-demand source"):
        build_target_data_plan(
            target_contexts=["AAA"],
            source_names=["not_a_source"],
            source_registry={},
            temporal_scope={"start": "2018-01-01", "end": "2021-01-01"},
        )


def test_target_plan_rejects_empty_target_contexts():
    """Planning requires at least one land-country context."""
    with pytest.raises(ValueError, match="no land-country contexts"):
        build_target_data_plan(
            target_contexts=[],
            source_names=["source_a"],
            source_registry={"source_a": {}},
            temporal_scope={"start": "2018-01-01", "end": "2021-01-01"},
        )


# ---------------------------------------------------------------------------
# Plan serialization
# ---------------------------------------------------------------------------


def test_write_target_data_plan_creates_json_file(tmp_path):
    """Target plans are written as readable JSON and parent dirs are created."""
    plan = {
        "version": 2,
        "target_contexts": ["AAA"],
        "active_sources": ["source_a"],
        "source_contexts": {"source_a": ["AAA"]},
        "source_temporal_scopes": {
            "source_a": {
                "start": "2018-01-01T00:00:00+00:00",
                "end": "2021-01-01T00:00:00+00:00",
            }
        },
    }

    output = tmp_path / "nested" / "target_data_plan.json"

    write_target_data_plan(plan=plan, output_path=output)

    assert output.exists()

    with output.open(encoding="utf-8") as file:
        written = json.load(file)

    assert written == plan
