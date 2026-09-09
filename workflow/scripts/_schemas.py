"""Schemas for key files."""

# ruff: noqa: UP007
import pandas as pd
from pandera.pandas import DataFrameModel, Field
from pandera.typing.geopandas import GeoSeries
from pandera.typing.pandas import Series


class OPSDLoad(DataFrameModel):
    """OPSD Download Class."""

    class Config:
        """OPSD Config class."""

        coerce = True
        strict = False

    region: Series[str]
    "2-letter country code."
    variable: Series[str]
    "Variable."
    attribute: Series[str]
    "Attribute."
    utc_timestamp: Series[pd.Timestamp]
    "UTC timestamp."
    data: Series[float]
    "Load data."


class Shapes(DataFrameModel):
    """Shapes Class."""

    class Config:
        """Shape config class."""

        coerce = True
        strict = False

    shape_id: Series[str]
    "Shape ID."
    country_id: Series[str]
    "Country ID."
    shape_class: Series[str] = Field(isin=["land", "maritime"])
    "Shape class."
    geometry: GeoSeries
    "Geometry."
