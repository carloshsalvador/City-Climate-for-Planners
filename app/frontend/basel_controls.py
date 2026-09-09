from __future__ import annotations

from app.runtime.basel_rc5 import BaselRc5Runtime


BASELINE_PAVED_ALBEDO = 0.1


def grass_percent_to_irrfrac(percent: float) -> float:
    return float(percent) / 100.0


def paved_albedo_for_cm3(*, cm3_enabled: bool, selected_paved_albedo: float) -> float:
    if not cm3_enabled:
        return BASELINE_PAVED_ALBEDO
    return float(selected_paved_albedo)


def default_financial_assumptions(runtime: BaselRc5Runtime) -> dict[str, float]:
    return {
        "water_unit_cost_chf_m3": float(runtime.cost_defaults["water_unit_cost_chf_m3"]["value"]),
        "whitening_unit_cost_chf_m2": float(
            runtime.cost_defaults["whitening_unit_cost_chf_m2"]["value"]
        ),
    }


def format_celsius(value: float) -> str:
    return f"{value:.3f} °C"


def format_chf(value: float) -> str:
    return f"CHF {value:,.0f}"


def format_m3(value: float) -> str:
    return f"{value:,.0f} m³"


def format_m2(value: float) -> str:
    return f"{value:,.0f} m²"
