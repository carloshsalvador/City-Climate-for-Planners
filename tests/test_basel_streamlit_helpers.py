from app.frontend.basel_controls import (
    BASELINE_PAVED_ALBEDO,
    default_financial_assumptions,
    grass_percent_to_irrfrac,
    paved_albedo_for_cm3,
)
from app.runtime import BaselRc5Runtime


def test_grass_percent_to_irrfrac_conversion():
    assert grass_percent_to_irrfrac(0) == 0.0
    assert grass_percent_to_irrfrac(35) == 0.35
    assert grass_percent_to_irrfrac(100) == 1.0


def test_cm3_off_forces_baseline_paved_albedo():
    assert paved_albedo_for_cm3(cm3_enabled=False, selected_paved_albedo=0.87) == 0.1
    assert paved_albedo_for_cm3(cm3_enabled=False, selected_paved_albedo=0.4) == BASELINE_PAVED_ALBEDO


def test_cm3_on_uses_selected_paved_albedo():
    assert paved_albedo_for_cm3(cm3_enabled=True, selected_paved_albedo=0.87) == 0.87
    assert paved_albedo_for_cm3(cm3_enabled=True, selected_paved_albedo=0.4) == 0.4


def test_default_financial_assumptions_come_from_runtime_bundle():
    runtime = BaselRc5Runtime()

    assert default_financial_assumptions(runtime) == {
        "water_unit_cost_chf_m3": 0.73,
        "whitening_unit_cost_chf_m2": 1.0,
    }
