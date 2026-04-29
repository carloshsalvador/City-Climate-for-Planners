from pydantic import BaseModel, Field, field_validator
from typing import Dict, List, Optional

class Coordinates(BaseModel):
    lat: float
    lon: float

class LandFractions(BaseModel):
    """Represents the percentage (0.0 to 1.0) of different land cover types."""
    paved: float = Field(..., ge=0.0, le=1.0)
    buildings: float = Field(..., ge=0.0, le=1.0)
    evergreen_trees: float = Field(..., ge=0.0, le=1.0)
    deciduous_trees: float = Field(..., ge=0.0, le=1.0)
    grass: float = Field(..., ge=0.0, le=1.0)
    bare_soil: float = Field(..., ge=0.0, le=1.0)
    water: float = Field(..., ge=0.0, le=1.0)

    @field_validator('*', mode='before')
    @classmethod
    def check_sum(cls, v):
        # We will implement a global sum check in the loader or a root validator 
        # if we want to be strict. For now, we allow individual changes.
        return v

class CityMetrics(BaseModel):
    mean_annual_temp: float
    max_annual_temp: float
    hot_days: float
    tropical_nights: float
    summer_days: float
    heat_risk_class: str

class CityIndicators(BaseModel):
    city: str
    baseline_year: int
    metrics: CityMetrics
    units: Dict[str, str]

class CityBaseline(BaseModel):
    location: str
    coordinates: Coordinates
    fractions: LandFractions
    description: str
