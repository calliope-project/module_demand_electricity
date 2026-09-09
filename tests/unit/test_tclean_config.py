"""Tests for the Modelblocks-to-T-Clean configuration adapter."""

import pandas as pd
import pytest
from _tclean_config import (
    CONSTRUCTED_SOURCE_NAME,
    build_advanced_rules,
    build_all_constructed_source_periods,
    build_basic_rules,
    build_data_quality_tests,
    build_scaling_source_periods,
    build_time_grid,
    filter_source_requests_by_temporal_scope,
)
from tclean import TimeGrid


def test_build_time_grid_translates_temporal_scope() -> None:
    """Test build time grid accepts temporal scope."""
    grid = build_time_grid(
        {
            "start": "2020-01-01T00:30:00Z",
            "end": "2020-01-01T03:30:00Z",
            "frequency": "1h",
        }
    )
    assert isinstance(grid, TimeGrid)
    assert grid.start == pd.Timestamp("2020-01-01T00:30:00Z")
    assert grid.end == pd.Timestamp("2020-01-01T03:30:00Z")
    assert grid.frequency == pd.Timedelta("1h")


def test_build_basic_rules_returns_no_rules_when_mode_is_off() -> None:
    """Test basic rules returns nothing when disabled."""
    config = {"mode": "off", "basic": {"rules": []}, "data_quality": {"tests": []}}
    assert build_basic_rules(config) == []


def test_build_basic_rules_preserves_configured_rule_order() -> None:
    """Test basic rules preserves order."""
    rules = [
        {"name": "first", "method": "linear_interpolation", "max_gap": "2h"},
        {
            "name": "second",
            "method": "copy_periods",
            "max_gap": "4h",
            "source_offsets": ["-24h"],
        },
    ]
    config = {"mode": "basic", "basic": {"rules": rules}, "data_quality": {"tests": []}}
    assert build_basic_rules(config) == rules


def test_build_advanced_rules_returns_canonical_columns_when_empty() -> None:
    """Test advanced returns column headers even when empty."""
    config = {
        "mode": "advanced",
        "basic": {"rules": []},
        "advanced": {"sources": {}, "rules": []},
        "data_quality": {"tests": []},
    }
    result = build_advanced_rules(config)
    assert result.empty
    assert list(result.columns) == [
        "rule_name",
        "method",
        "source",
        "context",
        "start",
        "end",
        "scope",
    ]


def test_build_scaling_source_periods_builds_match_total_periods() -> None:
    """Check match_total scaling periods are translated for T-Clean."""
    definition = {
        "method": "construct_from_sources",
        "periods": [
            {"country": "GBR", "start": "2024-01-01", "end": "2024-02-01", "weight": 1}
        ],
        "scaling": {
            "method": "match_total",
            "periods": [
                {
                    "country": "ALB",
                    "start": "2023-01-01",
                    "end": "2023-02-01",
                    "weight": 1,
                }
            ],
        },
    }

    result = build_scaling_source_periods(definition)

    assert result is not None
    assert result["context"].tolist() == ["ALB"]
    assert result["weight"].tolist() == [1]
    assert result["start"].tolist() == [pd.Timestamp("2023-01-01", tz="UTC")]
    assert result["end"].tolist() == [pd.Timestamp("2023-02-01", tz="UTC")]


def test_build_scaling_source_periods_returns_none_for_normalise_mean() -> None:
    """Check mean normalisation requires no auxiliary scaling periods."""
    definition = {
        "method": "construct_from_sources",
        "periods": [],
        "scaling": {"method": "normalise_mean"},
    }

    assert build_scaling_source_periods(definition) is None


def test_build_scaling_source_periods_returns_none_for_normalise_max() -> None:
    """Check maximum normalisation requires no auxiliary scaling periods."""
    definition = {
        "method": "construct_from_sources",
        "periods": [],
        "scaling": {"method": "normalise_max"},
    }

    assert build_scaling_source_periods(definition) is None


def test_normalisation_scaling_does_not_add_auxiliary_periods() -> None:
    """Check normalisation methods do not add scaling acquisition periods."""
    gap_filling_config = {
        "mode": "advanced",
        "advanced": {
            "sources": {
                "mean_source": {
                    "method": "construct_from_sources",
                    "periods": [
                        {
                            "country": "GBR",
                            "start": "2024-01-01",
                            "end": "2024-02-01",
                            "weight": 1,
                        }
                    ],
                    "scaling": {"method": "normalise_mean"},
                },
                "max_source": {
                    "method": "construct_from_sources",
                    "periods": [
                        {
                            "country": "FRA",
                            "start": "2024-01-01",
                            "end": "2024-02-01",
                            "weight": 1,
                        }
                    ],
                    "scaling": {"method": "normalise_max"},
                },
            }
        },
        "data_quality": {"tests": []},
    }

    result = build_all_constructed_source_periods(gap_filling_config)

    assert set(result) == {"mean_source", "max_source"}
    assert result["mean_source"]["context"].tolist() == ["GBR"]
    assert result["max_source"]["context"].tolist() == ["FRA"]


def test_match_total_scaling_adds_auxiliary_periods() -> None:
    """Check match_total adds reference periods to auxiliary acquisition."""
    gap_filling_config = {
        "mode": "advanced",
        "advanced": {
            "sources": {
                "scaled_source": {
                    "method": "construct_from_sources",
                    "periods": [
                        {
                            "country": "GBR",
                            "start": "2024-01-01",
                            "end": "2024-02-01",
                            "weight": 1,
                        }
                    ],
                    "scaling": {
                        "method": "match_total",
                        "periods": [
                            {
                                "country": "ALB",
                                "start": "2023-01-01",
                                "end": "2023-02-01",
                                "weight": 1,
                            }
                        ],
                    },
                }
            }
        },
        "data_quality": {"tests": []},
    }

    result = build_all_constructed_source_periods(gap_filling_config)

    assert set(result) == {"scaled_source"}
    assert result["scaled_source"]["context"].tolist() == ["GBR", "ALB"]


def test_auxiliary_temporal_filter_preserves_fully_available_request() -> None:
    """Check a provider covering the whole requirement is not clipped."""
    start = pd.Timestamp("2020-01-01", tz="UTC")
    end = pd.Timestamp("2020-02-01", tz="UTC")

    requests = pd.DataFrame(
        {"source": ["source_a"], "context": ["AAA"], "start": [start], "end": [end]}
    )

    requirements = pd.DataFrame({"context": ["AAA"], "start": [start], "end": [end]})

    result = filter_source_requests_by_temporal_scope(
        requests,
        requirements=requirements,
        source_registry={
            "source_a": {"temporal_scope": {"start": "2019-01-01", "end": "2021-01-01"}}
        },
    )

    assert len(result) == 1
    assert result.loc[0, "start"] == start
    assert result.loc[0, "end"] == end
    assert result.loc[0, "group_start"] == start
    assert result.loc[0, "group_end"] == end


def test_auxiliary_temporal_filter_clips_adjacent_providers() -> None:
    """Check adjacent providers are clipped to a shared requirement."""
    group_start = pd.Timestamp("2018-01-01", tz="UTC")
    boundary = pd.Timestamp("2019-01-01", tz="UTC")
    group_end = pd.Timestamp("2021-01-01", tz="UTC")

    requests = pd.DataFrame(
        {
            "source": ["old_source", "new_source"],
            "context": ["AAA", "AAA"],
            "start": [group_start, group_start],
            "end": [group_end, group_end],
        }
    )

    requirements = pd.DataFrame(
        {"context": ["AAA"], "start": [group_start], "end": [group_end]}
    )

    result = filter_source_requests_by_temporal_scope(
        requests,
        requirements=requirements,
        source_registry={
            "old_source": {
                "temporal_scope": {"start": "2005-01-01", "end": "2019-01-01"}
            },
            "new_source": {
                "temporal_scope": {"start": "2019-01-01", "end": "2026-01-01"}
            },
        },
    )

    old_source = result.loc[result["source"] == "old_source"].iloc[0]
    new_source = result.loc[result["source"] == "new_source"].iloc[0]

    assert old_source["start"] == group_start
    assert old_source["end"] == boundary

    assert new_source["start"] == boundary
    assert new_source["end"] == group_end

    assert old_source["group_start"] == group_start
    assert old_source["group_end"] == group_end
    assert new_source["group_start"] == group_start
    assert new_source["group_end"] == group_end


def test_auxiliary_temporal_filter_removes_non_overlapping_provider() -> None:
    """Check an unavailable provider is removed when another covers the period."""
    start = pd.Timestamp("2020-01-01", tz="UTC")
    end = pd.Timestamp("2021-01-01", tz="UTC")

    requests = pd.DataFrame(
        {
            "source": ["old_source", "current_source"],
            "context": ["AAA", "AAA"],
            "start": [start, start],
            "end": [end, end],
        }
    )

    requirements = pd.DataFrame({"context": ["AAA"], "start": [start], "end": [end]})

    result = filter_source_requests_by_temporal_scope(
        requests,
        requirements=requirements,
        source_registry={
            "old_source": {
                "temporal_scope": {"start": "2005-01-01", "end": "2019-01-01"}
            },
            "current_source": {
                "temporal_scope": {"start": "2019-01-01", "end": "2025-01-01"}
            },
        },
    )

    assert result["source"].tolist() == ["current_source"]
    assert result.loc[0, "start"] == start
    assert result.loc[0, "end"] == end


def test_auxiliary_temporal_filter_rejects_coverage_gap() -> None:
    """Check a temporal gap between providers is rejected."""
    start = pd.Timestamp("2018-01-01", tz="UTC")
    end = pd.Timestamp("2021-01-01", tz="UTC")

    requests = pd.DataFrame(
        {
            "source": ["old_source", "new_source"],
            "context": ["AAA", "AAA"],
            "start": [start, start],
            "end": [end, end],
        }
    )

    requirements = pd.DataFrame({"context": ["AAA"], "start": [start], "end": [end]})

    with pytest.raises(ValueError, match=r"2019-01-01T00:00:00\+00:00") as exc_info:
        filter_source_requests_by_temporal_scope(
            requests,
            requirements=requirements,
            source_registry={
                "old_source": {
                    "temporal_scope": {"start": "2005-01-01", "end": "2019-01-01"}
                },
                "new_source": {
                    "temporal_scope": {"start": "2019-02-01", "end": "2026-01-01"}
                },
            },
        )

    message = str(exc_info.value)

    assert "AAA" in message
    assert "2019-01-01T00:00:00+00:00" in message
    assert "2019-02-01T00:00:00+00:00" in message


def test_build_data_quality_tests_preserves_test_order() -> None:
    """Check data-quality test execution order is preserved."""
    config = {
        "tests": [
            {"name": "first", "method": "range"},
            {"name": "second", "method": "flatline"},
        ]
    }

    result = build_data_quality_tests(config)

    assert [test["name"] for test in result] == ["first", "second"]


def test_build_data_quality_tests_translates_countries_to_contexts() -> None:
    """Translate electricity-demand countries to generic T-Clean contexts."""
    config = {
        "tests": [
            {
                "name": "country_range",
                "method": "range",
                "countries": ["ALB", "MNE"],
                "minimum": {"value_mode": "fixed", "value": 0},
            }
        ]
    }

    result = build_data_quality_tests(config)

    assert result == [
        {
            "name": "country_range",
            "method": "range",
            "contexts": ["ALB", "MNE"],
            "sources": [CONSTRUCTED_SOURCE_NAME],
            "minimum": {"value_mode": "fixed", "value": 0},
        }
    ]


def test_build_data_quality_tests_defaults_to_constructed_source() -> None:
    """Apply data-quality tests to constructed demand by default."""
    config = {
        "tests": [
            {
                "name": "non_negative",
                "method": "range",
                "minimum": {"value_mode": "fixed", "value": 0},
            }
        ]
    }

    result = build_data_quality_tests(config)

    assert result[0]["sources"] == [CONSTRUCTED_SOURCE_NAME]


def test_build_data_quality_tests_preserves_sources() -> None:
    """Preserve explicitly configured source selectors."""
    config = {
        "tests": [
            {"name": "source_check", "method": "range", "sources": ["entsoe", "opsd"]}
        ]
    }

    result = build_data_quality_tests(config)

    assert result[0]["sources"] == ["entsoe", "opsd"]
