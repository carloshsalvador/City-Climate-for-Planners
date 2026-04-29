from .schemas import LandFractions

def apply_intervention(baseline: LandFractions, green_increase: float) -> LandFractions:
    """
    Simplistic logic to simulate an urban intervention.
    Increasing green space reduces paved area (asphalt).
    """
    # 1. Start with baseline
    new_fractions = baseline.model_copy()
    
    # 2. Add green (limit to 100%)
    actual_increase = min(green_increase, 1.0 - baseline.deciduous_trees - baseline.evergreen_trees - baseline.grass)
    
    # Divide increase between grass and deciduous trees (50/50 for demo)
    half = actual_increase / 2
    new_fractions.deciduous_trees += half
    new_fractions.grass += half
    
    # 3. Subtract from paved (limit to 0%)
    new_fractions.paved = max(0.0, baseline.paved - actual_increase)
    
    # If paved wasn't enough, subtract from bare_soil
    remaining = actual_increase - (baseline.paved - new_fractions.paved)
    if remaining > 0:
        new_fractions.bare_soil = max(0.0, baseline.bare_soil - remaining)
        
    return new_fractions

def estimate_delta_t(new_fractions: LandFractions, baseline: LandFractions) -> float:
    """
    A simplified 'Surrogate Model' for the prototype.
    In a real scenario, this would be a Machine Learning model or SUEWS output.
    Rule of thumb: -0.2°C for every 10% increase in green space.
    """
    baseline_green = baseline.deciduous_trees + baseline.evergreen_trees + baseline.grass
    new_green = new_fractions.deciduous_trees + new_fractions.evergreen_trees + new_fractions.grass
    
    increase = new_green - baseline_green
    delta_t = (increase / 0.1) * -0.2
    
    return round(delta_t, 2)
