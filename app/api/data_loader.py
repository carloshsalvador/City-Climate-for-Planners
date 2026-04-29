import json
from pathlib import Path
from typing import Optional
from .schemas import CityBaseline, CityIndicators

# Base path relative to the root of the project
DATA_DIR = Path(__file__).parent.parent.parent / "data" / "sample"

def load_city_baseline(city_name: str = "basel") -> CityBaseline:
    """Loads the baseline land fractions for a specific city."""
    file_path = DATA_DIR / f"{city_name.lower()}_land_fractions.json"
    
    if not file_path.exists():
        raise FileNotFoundError(f"Baseline data for {city_name} not found at {file_path}")
        
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return CityBaseline(**data) # '**data' unpacks the data dict into keyword arguments, e.g. **{'a': 1, 'b': 2} becomes a=1, b=2. Pydantic then validates that these arguments match the expected types (float, etc.) for the CityBaseline model.

def load_city_indicators(city_name: str = "basel") -> CityIndicators:
    """Loads the climate indicators (metrics) for a specific city."""
    file_path = DATA_DIR / "baseline_indicators.json" # Assuming one file for now
    
    if not file_path.exists():
        raise FileNotFoundError(f"Indicator data not found at {file_path}")
        
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        # In a real app, we might filter by city_name inside the JSON
        return CityIndicators(**data) # '**data' unpacks the data dict into keyword arguments, e.g. **{'a': 1, 'b': 2} becomes a=1, b=2. Pydantic then validates that these arguments match the expected types (float, etc.) for the CityBaseline model.
