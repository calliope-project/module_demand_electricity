"""Tests for module/provider-specific Pandera schemas."""

import pandas as pd
import pytest
from _schemas import OPSDLoad, Shapes
from pandera.errors import SchemaError


def test_opsd_schema_accepts_provider_rows() -> None:
    """Test OPSD schema accepts provider rows."""
    frame = pd.DataFrame(
        {
            "region": ["GB"],
            "variable": ["load"],
            "attribute": ["actual"],
            "utc_timestamp": [pd.Timestamp("2020-01-01T00:00:00Z")],
            "data": [42.0],
        }
    )
    validated = OPSDLoad.validate(frame)
    assert validated.loc[0, "data"] == 42.0


def test_shapes_schema_rejects_unknown_shape_class() -> None:
    """Tests shapes schema rejects unknown shape class."""
    frame = pd.DataFrame(
        {
            "shape_id": ["x"],
            "country_id": ["GBR"],
            "shape_class": ["unknown"],
            "geometry": [None],
        }
    )
    with pytest.raises(SchemaError):
        Shapes.validate(frame)
