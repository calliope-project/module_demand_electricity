"""Tests for semantic module configuration validation."""

import pytest
from validate_config import validate_data_quality_config_semantics


def _config_with_data_quality(tests: list[dict]) -> dict:
    """Return minimal configuration for data-quality semantic validation."""
    return {
        "temporal_scope": {
            "start": "2020-01-01",
            "end": "2020-01-03",
            "frequency": "1h",
        },
        "data_quality": {"tests": tests},
    }


def test_data_quality_semantics_accept_valid_range_test() -> None:
    """Accept a valid module data-quality test through T-Clean."""
    config = _config_with_data_quality(
        [
            {
                "name": "non_negative",
                "method": "range",
                "minimum": {"value_mode": "fixed", "value": 0},
            }
        ]
    )

    validate_data_quality_config_semantics(config)


def test_data_quality_semantics_reject_invalid_value_spec() -> None:
    """Reject malformed method configuration through T-Clean."""
    config = _config_with_data_quality(
        [{"name": "non_negative", "method": "range", "minimum": 0}]
    )

    with pytest.raises(ValueError, match="value specification"):
        validate_data_quality_config_semantics(config)
