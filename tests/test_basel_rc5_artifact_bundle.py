import csv
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import joblib
import numpy as np
from sklearn.pipeline import Pipeline


BUNDLE_DIR = Path(__file__).resolve().parents[1] / "app" / "artifacts" / "basel_rc5_app_v1"
FEATURE_ORDER = ["grass_irrfrac", "paved_albedo"]
MODEL_TARGETS = {
    "annual_mean_delta_t2": "annual_delta_t2",
    "warm_season_daytime_mean_delta_t2": "warm_day_delta_t2",
    "warm_season_nighttime_mean_delta_t2": "warm_night_delta_t2",
    "irr_total_raw": "irrigation_raw_mm",
}


def _load_json(relative_path: str) -> dict:
    with (BUNDLE_DIR / relative_path).open(encoding="utf-8") as handle:
        return json.load(handle)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_manifest_hashes_and_expected_files_match_promoted_bundle():
    manifest = _load_json("manifest.json")

    expected_runtime_files = {
        "manifest.json",
        "README.md",
        "models/portable/annual_mean_delta_t2.joblib",
        "models/portable/warm_season_daytime_mean_delta_t2.joblib",
        "models/portable/warm_season_nighttime_mean_delta_t2.joblib",
        "models/portable/cumulative_irrigation.joblib",
        "training_context/rc5_context.json",
        "operational/consequence_contract.json",
        "financial/cost_defaults.json",
        "validation/golden_predictions.csv",
        "validation/golden_app_contract.json",
    }

    for relative_path in expected_runtime_files:
        assert (BUNDLE_DIR / relative_path).is_file(), relative_path

    assert not (BUNDLE_DIR / "models" / "cumulative_irrigation.joblib").exists()

    for relative_path, expected_hash in manifest["hashes"].items():
        assert _sha256(BUNDLE_DIR / relative_path) == expected_hash, relative_path


def test_portable_models_load_without_private_analysis_dependency():
    manifest = _load_json("manifest.json")

    assert importlib.util.find_spec("analysis") is None
    sys.modules.pop("analysis", None)

    for model_entry in manifest["models"]:
        assert model_entry["runtime_class"] == "sklearn.pipeline.Pipeline"
        assert model_entry["feature_order"] == FEATURE_ORDER
        assert model_entry["features"] == FEATURE_ORDER

        model = joblib.load(BUNDLE_DIR / model_entry["runtime_path"])

        assert isinstance(model, Pipeline)
        assert "analysis" not in sys.modules
        assert getattr(model, "n_features_in_", 2) == 2


def test_bundle_relative_paths_and_fixed_context_boundary_are_explicit():
    manifest = _load_json("manifest.json")
    context = _load_json(manifest["training_context"]["runtime_path"])

    assert (BUNDLE_DIR / manifest["training_context"]["runtime_path"]).is_file()
    assert (BUNDLE_DIR / manifest["operational_financial"]["consequence_contract_runtime_path"]).is_file()
    assert (BUNDLE_DIR / manifest["operational_financial"]["cost_defaults_runtime_path"]).is_file()
    assert (BUNDLE_DIR / manifest["validation"]["golden_predictions_runtime_path"]).is_file()
    assert (BUNDLE_DIR / manifest["validation"]["golden_app_contract_runtime_path"]).is_file()

    assert manifest["applicability"]["basel_rc5_only"] is True
    assert "Dynamic SuewsSiteContext" in manifest["applicability"]["dynamic_site_context_incompatibility"]
    assert manifest["applicability"]["surrogate_mapping"] == (
        "Y = f(grass_irrfrac, paved_albedo | fixed Basel rc5 context)"
    )

    assert context["context_type"] == "fixed_surrogate_training_context"
    assert context["not_dynamic_site_context"] is True
    assert context["site_area_m2"]["classification"] == "provisional_fixed_training_context_quantity"
    assert context["paved_fraction"]["classification"] == "canonical_fixed_training_context_quantity"
    assert context["latitude"]["classification"] == "provisional_context_coordinate"
    assert context["longitude"]["classification"] == "provisional_context_coordinate"
    assert context["spatial_configuration"]["radius_or_geometry_mode"]["classification"] == "unresolved"


def test_golden_scientific_replay_uses_only_promoted_portable_bundle():
    manifest = _load_json("manifest.json")
    models = {entry["target"]: joblib.load(BUNDLE_DIR / entry["runtime_path"]) for entry in manifest["models"]}
    tolerances = {entry["target"]: entry["parity"]["tolerance"] for entry in manifest["models"]}

    with (BUNDLE_DIR / "validation" / "golden_predictions.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert rows

    features = np.array([[float(row[name]) for name in FEATURE_ORDER] for row in rows])
    for target, golden_column in MODEL_TARGETS.items():
        predictions = models[target].predict(features)
        expected = np.array([float(row[golden_column]) for row in rows])

        assert np.allclose(predictions, expected, rtol=0.0, atol=tolerances[target]), target
