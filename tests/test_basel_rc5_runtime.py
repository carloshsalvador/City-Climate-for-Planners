import json
import math
from dataclasses import asdict
from pathlib import Path

import pytest

from app.runtime.basel_rc5 import (
    FEATURE_ORDER,
    REQUIRED_MODEL_TARGETS,
    BaselRc5CompatibilityError,
    BaselRc5InputError,
    BaselRc5Runtime,
)


BUNDLE_DIR = Path(__file__).resolve().parents[1] / "app" / "artifacts" / "basel_rc5_app_v1"
APP_CONTRACT_ABS_TOL = 1e-6
APP_CONTRACT_REL_TOL = 1e-8


@pytest.fixture(scope="module")
def runtime() -> BaselRc5Runtime:
    return BaselRc5Runtime()


def _golden_contract() -> dict:
    with (BUNDLE_DIR / "validation" / "golden_app_contract.json").open(encoding="utf-8") as handle:
        return json.load(handle)


def _assert_close(actual: float, expected: float, *, tol: float = APP_CONTRACT_ABS_TOL) -> None:
    assert math.isclose(actual, expected, rel_tol=APP_CONTRACT_REL_TOL, abs_tol=tol)


def _assert_result_matches_contract(actual: dict, expected: dict) -> None:
    for section in ("scientific", "planner", "operational", "financial"):
        for key, expected_value in expected[section].items():
            _assert_close(actual[section][key], expected_value)

    for key, expected_value in expected["metadata"].items():
        assert actual["metadata"][key] == expected_value


def _evaluate_golden(runtime: BaselRc5Runtime, scenario_id: str) -> dict:
    scenario = next(
        item for item in _golden_contract()["scenarios"] if item["scenario_id"] == scenario_id
    )
    return runtime.evaluate(
        grass_irrfrac=scenario["grass_irrfrac"],
        paved_albedo=scenario["paved_albedo"],
        cm3_enabled=scenario["cm3_enabled"],
    ).to_dict()


def test_runtime_initialization_loads_bundle_and_four_models(runtime):
    assert runtime.bundle_root == BUNDLE_DIR.resolve()
    assert runtime.manifest["bundle"]["version"] == "basel_rc5_app_v1"
    assert set(runtime.models) == set(REQUIRED_MODEL_TARGETS)


def test_feature_order_comes_from_validated_contract(runtime):
    assert runtime.feature_order == FEATURE_ORDER
    for entry in runtime.manifest["models"]:
        assert tuple(entry["feature_order"]) == FEATURE_ORDER


def test_default_financial_assumptions(runtime):
    result = runtime.evaluate(grass_irrfrac=1.0, paved_albedo=0.1, cm3_enabled=False)

    assert result.financial.water_unit_cost_chf_m3 == 0.73
    assert result.financial.whitening_unit_cost_chf_m2 == 1.0
    assert result.metadata.financial_assumption_statuses == {
        "water_unit_cost_chf_m3": "provisional_user_configurable",
        "whitening_unit_cost_chf_m2": "illustrative_user_configurable",
    }
    assert result.metadata.cost_assumption_status == "illustrative user-configurable assumption"


def test_custom_unit_cost_override(runtime):
    result = runtime.evaluate(
        grass_irrfrac=1.0,
        paved_albedo=0.87,
        cm3_enabled=True,
        water_unit_cost_chf_m3=2.0,
        whitening_unit_cost_chf_m2=3.0,
    )

    assert result.financial.water_unit_cost_chf_m3 == 2.0
    assert result.financial.whitening_unit_cost_chf_m2 == 3.0
    _assert_close(
        result.financial.irrigation_cost_chf,
        result.operational.water_volume_m3 * 2.0,
    )
    _assert_close(
        result.financial.whitening_cost_chf,
        result.operational.whitening_area_m2 * 3.0,
    )


def test_canonical_baseline_zeroes_irrigation_consequences(runtime):
    result = runtime.evaluate(grass_irrfrac=0.0, paved_albedo=0.1, cm3_enabled=False)

    assert result.operational.irrigation_mm == 0.0
    assert result.operational.water_volume_m3 == 0.0
    assert result.financial.irrigation_cost_chf == 0.0


@pytest.mark.parametrize(
    "scenario_id",
    [
        "ANC_BS1G_MAX",
        "ANC_CM3_MAX",
        "ANC_JOINT_MAX",
        "APP_INTERIOR_GRASS030_ALBEDO040",
    ],
)
def test_named_golden_scenarios(runtime, scenario_id):
    scenario = next(
        item for item in _golden_contract()["scenarios"] if item["scenario_id"] == scenario_id
    )

    actual = _evaluate_golden(runtime, scenario_id)

    _assert_result_matches_contract(actual, scenario["contract"])


def test_out_of_domain_grass_irrfrac_rejected(runtime):
    with pytest.raises(BaselRc5InputError):
        runtime.evaluate(grass_irrfrac=1.01, paved_albedo=0.1, cm3_enabled=False)


def test_out_of_domain_paved_albedo_rejected(runtime):
    with pytest.raises(BaselRc5InputError):
        runtime.evaluate(grass_irrfrac=0.0, paved_albedo=0.871, cm3_enabled=False)


def test_nan_rejected(runtime):
    with pytest.raises(BaselRc5InputError):
        runtime.evaluate(grass_irrfrac=float("nan"), paved_albedo=0.1, cm3_enabled=False)


def test_infinity_rejected(runtime):
    with pytest.raises(BaselRc5InputError):
        runtime.evaluate(grass_irrfrac=0.0, paved_albedo=float("inf"), cm3_enabled=False)


def test_exact_training_context_use(runtime):
    result = runtime.evaluate(grass_irrfrac=1.0, paved_albedo=0.87, cm3_enabled=True)

    assert runtime.site_area_m2 == 785000.0
    assert runtime.paved_fraction == 0.3640046979865772
    _assert_close(
        result.operational.water_volume_m3,
        result.operational.irrigation_mm * runtime.site_area_m2 / 1000.0,
    )
    _assert_close(
        result.operational.whitening_area_m2,
        runtime.site_area_m2 * runtime.paved_fraction,
    )


def test_dynamic_site_parameters_are_not_accepted(runtime):
    with pytest.raises(TypeError):
        runtime.evaluate(
            grass_irrfrac=0.0,
            paved_albedo=0.1,
            cm3_enabled=False,
            latitude=47.5596,
        )


def test_complete_golden_replay(runtime):
    for scenario in _golden_contract()["scenarios"]:
        actual = runtime.evaluate(
            grass_irrfrac=scenario["grass_irrfrac"],
            paved_albedo=scenario["paved_albedo"],
            cm3_enabled=scenario["cm3_enabled"],
        ).to_dict()

        _assert_result_matches_contract(actual, scenario["contract"])


def test_runtime_version_compatibility_handling(monkeypatch):
    def fake_version(name):
        versions = {
            "scikit-learn": "0.0.0",
            "joblib": "1.5.3",
        }
        return versions[name]

    monkeypatch.setattr("app.runtime.basel_rc5.metadata.version", fake_version)

    with pytest.raises(BaselRc5CompatibilityError):
        BaselRc5Runtime()


def test_result_does_not_expose_raw_models(runtime):
    result = runtime.evaluate(grass_irrfrac=0.3, paved_albedo=0.4, cm3_enabled=True)

    assert "models" not in asdict(result)
