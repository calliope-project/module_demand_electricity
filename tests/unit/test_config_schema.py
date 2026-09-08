"""Tests for the module configuration schema."""

from pathlib import Path

import yaml
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPOSITORY_ROOT / "config" / "config.yaml"
SCHEMA_PATH = REPOSITORY_ROOT / "workflow" / "internal" / "config.schema.yaml"


def _format_validation_error(error: ValidationError) -> str:
    path = ".".join(str(part) for part in error.absolute_path)
    return f"{path or '<root>'}: {error.message}"


def _validate(config: dict) -> list[ValidationError]:
    with SCHEMA_PATH.open(encoding="utf-8") as schema_file:
        schema = yaml.safe_load(schema_file)
    return list(Draft202012Validator(schema).iter_errors(config))


def test_default_config_matches_schema() -> None:
    """Check default config matches schema."""
    with CONFIG_PATH.open(encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    errors = _validate(config)
    assert not errors, "\n".join(_format_validation_error(error) for error in errors)


def test_advanced_mode_allows_no_sources_or_rules() -> None:
    """Check advanced mode permits no arguments."""
    config = {
        "temporal_scope": {
            "start": "2021-01-01",
            "end": "2022-01-01",
            "frequency": "1h",
        },
        "load_sources": ["entsoe"],
        "gap_filling": {
            "mode": "advanced",
            "basic": {"rules": []},
            "advanced": {
                "auxiliary_data": {"basic_cleaning": {"enabled": True}},
                "sources": {},
                "rules": [],
            },
        },
        "data_quality": {"tests": []},
    }
    errors = _validate(config)
    assert not errors, "\n".join(_format_validation_error(error) for error in errors)


def _advanced_config_with_scaling(scaling: dict) -> dict:
    return {
        "temporal_scope": {
            "start": "2021-01-01",
            "end": "2022-01-01",
            "frequency": "1h",
        },
        "load_sources": ["entsoe"],
        "gap_filling": {
            "mode": "advanced",
            "basic": {"rules": []},
            "advanced": {
                "auxiliary_data": {"basic_cleaning": {"enabled": True}},
                "sources": {
                    "constructed": {
                        "method": "construct_from_sources",
                        "periods": [
                            {
                                "country": "ALB",
                                "start": "2020-01-01",
                                "end": "2020-01-02",
                                "weight": 1,
                            }
                        ],
                        "scaling": scaling,
                    }
                },
                "rules": [],
            },
        },
        "data_quality": {"tests": []},
    }


def test_constructed_source_allows_match_total_scaling() -> None:
    """Check for match_total method."""
    config = _advanced_config_with_scaling(
        {
            "method": "match_total",
            "periods": [
                {
                    "country": "ALB",
                    "start": "2020-01-01",
                    "end": "2020-01-02",
                    "weight": 1,
                }
            ],
        }
    )

    assert not _validate(config)


def test_constructed_source_allows_normalise_mean_scaling() -> None:
    """Check normalise mean method."""
    config = _advanced_config_with_scaling({"method": "normalise_mean"})

    assert not _validate(config)


def test_constructed_source_allows_normalise_max_scaling() -> None:
    """Check normalise max method."""
    config = _advanced_config_with_scaling({"method": "normalise_max"})

    assert not _validate(config)


def test_match_total_scaling_requires_periods() -> None:
    """Check match_total required periods."""
    config = _advanced_config_with_scaling({"method": "match_total"})

    assert _validate(config)


def test_normalise_mean_scaling_rejects_periods() -> None:
    """Check norm mean rejects additional args."""
    config = _advanced_config_with_scaling(
        {
            "method": "normalise_mean",
            "periods": [
                {
                    "country": "ALB",
                    "start": "2020-01-01",
                    "end": "2020-01-02",
                    "weight": 1,
                }
            ],
        }
    )

    assert _validate(config)


def test_normalise_max_scaling_rejects_periods() -> None:
    """Check norm max rejects additional args."""
    config = _advanced_config_with_scaling(
        {
            "method": "normalise_max",
            "periods": [
                {
                    "country": "ALB",
                    "start": "2020-01-01",
                    "end": "2020-01-02",
                    "weight": 1,
                }
            ],
        }
    )

    assert _validate(config)


def test_constructed_source_rejects_unknown_scaling_method() -> None:
    """Check rejection of unknown methods."""
    config = _advanced_config_with_scaling({"method": "something_else"})

    assert _validate(config)


def _config_with_data_quality(data_quality: dict) -> dict:
    """Return a minimal valid config with the supplied data-quality section."""
    return {
        "temporal_scope": {
            "start": "2021-01-01",
            "end": "2022-01-01",
            "frequency": "1h",
        },
        "load_sources": ["entsoe"],
        "data_quality": data_quality,
        "gap_filling": {
            "mode": "off",
            "basic": {"rules": []},
            "advanced": {
                "auxiliary_data": {
                    "basic_cleaning": {"enabled": True},
                },
                "sources": {},
                "rules": [],
            },
        },
    }

def test_data_quality_allows_no_tests() -> None:
    """Check data-quality configuration may contain no tests."""
    config = _config_with_data_quality({"tests": []})

    assert not _validate(config)

def test_data_quality_rejects_contexts_selector() -> None:
    """Require module-facing country terminology instead of T-Clean contexts."""
    config = _config_with_data_quality(
        {
            "tests": [
                {
                    "name": "example_range",
                    "method": "range",
                    "contexts": ["ALB"],
                }
            ]
        }
    )

    assert _validate(config)

