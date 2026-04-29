def calculate_intervention_costs(
    paved_removed_m2: float, 
    trees_planted_m2: float, 
    grass_planted_m2: float
) -> float:
    """
    Calculates estimated costs for the urban intervention.
    Unit costs (fictional for demo):
    - Pavement removal: 30 EUR/m2
    - Tree planting (incl. soil): 150 EUR/m2
    - Grass/Lawn: 40 EUR/m2
    """
    cost_paved = paved_removed_m2 * 30
    cost_trees = trees_planted_m2 * 150
    cost_grass = grass_planted_m2 * 40
    
    total_cost = cost_paved + cost_trees + cost_grass
    return round(total_cost, 2)

def get_cost_summary(total_area_m2: float, green_increase_fraction: float) -> dict:
    """Provides a human-readable cost summary."""
    area_to_change = total_area_m2 * green_increase_fraction
    
    # Simple split: 50% trees, 50% grass
    tree_area = area_to_change * 0.5
    grass_area = area_to_change * 0.5
    
    total_cost = calculate_intervention_costs(area_to_change, tree_area, grass_area)
    
    return {
        "total_cost": total_cost,
        "area_affected_m2": round(area_to_change, 2),
        "currency": "EUR"
    }
