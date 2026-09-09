from app.frontend.basel_controls import (
    BASELINE_PAVED_ALBEDO,
    default_financial_assumptions,
    format_celsius,
    format_chf,
    format_m2,
    format_m3,
    grass_percent_to_irrfrac,
    paved_albedo_for_cm3,
)
from app.runtime import BaselRc5Runtime


FRONTEND_DIR = BaselRc5Runtime().bundle_root.parents[1] / "frontend"


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


def test_planner_formatting_helpers_use_readable_units():
    assert format_celsius(0.12345) == "0.123 °C"
    assert format_chf(1234.56) == "CHF 1,235"
    assert format_m3(1234.56) == "1,235 m³"
    assert format_m2(1234.56) == "1,235 m²"


def test_home_page_declares_basel_as_only_active_validated_demonstrator():
    source = (FRONTEND_DIR / "streamlit_app.py").read_text(encoding="utf-8")

    assert 'value="Basel rc5"' in source
    assert "Additional cities and dynamic site geometries are not yet validated." in source
    assert "selectbox" not in source
    assert "Zurich" not in source
    assert "Berlin" not in source


def test_frontend_helpers_do_not_contain_scientific_consequence_formulas():
    source = (FRONTEND_DIR / "basel_controls.py").read_text(encoding="utf-8")

    assert "predict(" not in source
    assert "water_volume" not in source
    assert "whitening_area" not in source
    assert "irrigation_cost" not in source
