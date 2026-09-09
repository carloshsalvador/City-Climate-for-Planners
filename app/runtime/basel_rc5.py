from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib import metadata
import json
import math
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.pipeline import Pipeline


FEATURE_ORDER = ("grass_irrfrac", "paved_albedo")
REQUIRED_MODEL_TARGETS = {
    "annual_mean_delta_t2": "annual_delta_t2",
    "warm_season_daytime_mean_delta_t2": "warm_day_delta_t2",
    "warm_season_nighttime_mean_delta_t2": "warm_night_delta_t2",
    "irr_total_raw": "irrigation_raw_mm",
}
DEFAULT_BUNDLE_ROOT = Path(__file__).resolve().parents[1] / "artifacts" / "basel_rc5_app_v1"
BASEL_ONLY_VALIDITY = (
    "Basel-only rc5 Bachelorarbeit surrogate layer; do not transfer to other cities without "
    "city-specific validation."
)


class BaselRc5RuntimeError(RuntimeError):
    """Base exception for Basel rc5 runtime failures."""


class BaselRc5CompatibilityError(BaselRc5RuntimeError):
    """Raised when runtime libraries do not match the persisted bundle policy."""


class BaselRc5InputError(ValueError):
    """Raised when scenario inputs fall outside the validated surrogate domain."""


@dataclass(frozen=True)
class ScientificResult:
    annual_delta_t2: float
    warm_day_delta_t2: float
    warm_night_delta_t2: float
    irrigation_raw_mm: float


@dataclass(frozen=True)
class PlannerResult:
    annual_cooling: float
    warm_day_cooling: float
    warm_night_cooling: float


@dataclass(frozen=True)
class OperationalResult:
    irrigation_mm: float
    water_volume_m3: float
    whitening_area_m2: float


@dataclass(frozen=True)
class FinancialResult:
    water_unit_cost_chf_m3: float
    whitening_unit_cost_chf_m2: float
    irrigation_cost_chf: float
    whitening_cost_chf: float
    total_variable_cost_chf: float


@dataclass(frozen=True)
class RuntimeMetadata:
    city: str
    bundle_version: str
    model_version: str
    source_run: str
    training_context_id: str
    basel_only_validity: str
    applicability_statement: str
    cost_assumption_status: str
    is_canonical_basel_baseline: bool
    financial_assumption_statuses: dict[str, str]


@dataclass(frozen=True)
class BaselRc5Result:
    scientific: ScientificResult
    planner: PlannerResult
    operational: OperationalResult
    financial: FinancialResult
    metadata: RuntimeMetadata

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BaselRc5Runtime:
    """Application-facing inference engine for the fixed Basel rc5 bundle."""

    def __init__(self, bundle_root: str | Path | None = None, *, strict_versions: bool = True) -> None:
        self.bundle_root = Path(bundle_root) if bundle_root is not None else DEFAULT_BUNDLE_ROOT
        self.bundle_root = self.bundle_root.resolve()
        self.strict_versions = strict_versions

        self.manifest = self._load_json("manifest.json")
        self.training_context = self._load_json(self.manifest["training_context"]["runtime_path"])
        self.cost_defaults = self._load_json(
            self.manifest["operational_financial"]["cost_defaults_runtime_path"]
        )
        self.consequence_contract = self._load_json(
            self.manifest["operational_financial"]["consequence_contract_runtime_path"]
        )

        self._feature_ranges = self._read_feature_ranges()
        self._validate_manifest_contract()
        self._validate_runtime_versions()
        self.models = self._load_models()

    @property
    def feature_order(self) -> tuple[str, str]:
        return FEATURE_ORDER

    def evaluate(
        self,
        *,
        grass_irrfrac: float,
        paved_albedo: float,
        cm3_enabled: bool,
        water_unit_cost_chf_m3: float | None = None,
        whitening_unit_cost_chf_m2: float | None = None,
    ) -> BaselRc5Result:
        features = self._validate_features(
            grass_irrfrac=grass_irrfrac,
            paved_albedo=paved_albedo,
        )
        costs = self._resolve_unit_costs(
            water_unit_cost_chf_m3=water_unit_cost_chf_m3,
            whitening_unit_cost_chf_m2=whitening_unit_cost_chf_m2,
        )

        x = np.array([[features[name] for name in FEATURE_ORDER]], dtype=float)
        predictions = {
            target: float(model.predict(x)[0])
            for target, model in self.models.items()
        }

        scientific = ScientificResult(
            annual_delta_t2=predictions["annual_mean_delta_t2"],
            warm_day_delta_t2=predictions["warm_season_daytime_mean_delta_t2"],
            warm_night_delta_t2=predictions["warm_season_nighttime_mean_delta_t2"],
            irrigation_raw_mm=predictions["irr_total_raw"],
        )
        planner = PlannerResult(
            annual_cooling=-scientific.annual_delta_t2,
            warm_day_cooling=-scientific.warm_day_delta_t2,
            warm_night_cooling=-scientific.warm_night_delta_t2,
        )

        irrigation_mm = max(0.0, scientific.irrigation_raw_mm)
        water_volume_m3 = irrigation_mm * self.site_area_m2 / 1000.0
        irrigation_cost_chf = water_volume_m3 * costs["water_unit_cost_chf_m3"]

        if self._is_canonical_baseline(features, cm3_enabled=cm3_enabled):
            irrigation_mm = 0.0
            water_volume_m3 = 0.0
            irrigation_cost_chf = 0.0

        whitening_area_m2 = self.site_area_m2 * self.paved_fraction if cm3_enabled else 0.0
        whitening_cost_chf = whitening_area_m2 * costs["whitening_unit_cost_chf_m2"]

        operational = OperationalResult(
            irrigation_mm=irrigation_mm,
            water_volume_m3=water_volume_m3,
            whitening_area_m2=whitening_area_m2,
        )
        financial = FinancialResult(
            water_unit_cost_chf_m3=costs["water_unit_cost_chf_m3"],
            whitening_unit_cost_chf_m2=costs["whitening_unit_cost_chf_m2"],
            irrigation_cost_chf=irrigation_cost_chf,
            whitening_cost_chf=whitening_cost_chf,
            total_variable_cost_chf=irrigation_cost_chf + whitening_cost_chf,
        )

        return BaselRc5Result(
            scientific=scientific,
            planner=planner,
            operational=operational,
            financial=financial,
            metadata=self._metadata(
                is_canonical_basel_baseline=self._is_canonical_baseline(
                    features,
                    cm3_enabled=cm3_enabled,
                )
            ),
        )

    @property
    def site_area_m2(self) -> float:
        return float(self.training_context["site_area_m2"]["value"])

    @property
    def paved_fraction(self) -> float:
        return float(self.training_context["paved_fraction"]["value"])

    def _load_json(self, relative_path: str) -> dict[str, Any]:
        path = self.bundle_root / relative_path
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)

    def _read_feature_ranges(self) -> dict[str, tuple[float, float]]:
        ranges: dict[str, tuple[float, float]] = {}
        for item in self.manifest["applicability"]["feature_domain_constraints"]:
            ranges[item["feature"]] = (float(item["min"]), float(item["max"]))
        return ranges

    def _validate_manifest_contract(self) -> None:
        if not self.manifest.get("bundle", {}).get("version"):
            raise BaselRc5RuntimeError("Basel rc5 bundle version is missing")
        if self.manifest.get("applicability", {}).get("basel_rc5_only") is not True:
            raise BaselRc5RuntimeError("Basel rc5 applicability flag is missing or false")
        if not self.manifest.get("applicability", {}).get("dynamic_site_context_incompatibility"):
            raise BaselRc5RuntimeError("Dynamic site-context incompatibility metadata is missing")
        if self.training_context.get("context_type") != "fixed_surrogate_training_context":
            raise BaselRc5RuntimeError("Fixed training-context metadata is missing")
        if self.training_context.get("not_dynamic_site_context") is not True:
            raise BaselRc5RuntimeError("Training context must be explicitly non-dynamic")

        model_entries = self.manifest.get("models", [])
        targets = {entry.get("target") for entry in model_entries}
        if targets != set(REQUIRED_MODEL_TARGETS):
            raise BaselRc5RuntimeError(f"Expected exactly four model targets, got {sorted(targets)}")

        for entry in model_entries:
            if tuple(entry.get("feature_order", ())) != FEATURE_ORDER:
                raise BaselRc5RuntimeError(f"Unexpected feature order for {entry.get('target')}")
            if entry.get("runtime_class") != "sklearn.pipeline.Pipeline":
                raise BaselRc5RuntimeError(f"Unexpected runtime class for {entry.get('target')}")

    def _validate_runtime_versions(self) -> None:
        if not self.strict_versions:
            return

        expected = self.manifest["runtime"]
        actual = {
            "numpy": np.__version__,
            "scikit-learn": metadata.version("scikit-learn"),
            "joblib": metadata.version("joblib"),
        }
        required = {
            "numpy": expected["numpy_version"],
            "scikit-learn": expected["scikit_learn_version"],
            "joblib": expected["joblib_version"],
        }

        mismatches = [
            f"{name}: expected {required[name]}, got {actual[name]}"
            for name in required
            if actual[name] != required[name]
        ]
        if mismatches:
            raise BaselRc5CompatibilityError(
                "Basel rc5 bundle runtime library mismatch: " + "; ".join(mismatches)
            )

    def _load_models(self) -> dict[str, Pipeline]:
        models: dict[str, Pipeline] = {}
        for entry in self.manifest["models"]:
            model = joblib.load(self.bundle_root / entry["runtime_path"])
            if not isinstance(model, Pipeline):
                raise BaselRc5RuntimeError(
                    f"Loaded model {entry['target']} is {type(model)!r}, expected sklearn Pipeline"
                )
            models[entry["target"]] = model
        return models

    def _validate_features(self, *, grass_irrfrac: float, paved_albedo: float) -> dict[str, float]:
        values = {
            "grass_irrfrac": grass_irrfrac,
            "paved_albedo": paved_albedo,
        }
        for feature, value in values.items():
            if value is None:
                raise BaselRc5InputError(f"{feature} is required")
            try:
                numeric = float(value)
            except (TypeError, ValueError) as exc:
                raise BaselRc5InputError(f"{feature} must be numeric") from exc
            if math.isnan(numeric) or math.isinf(numeric):
                raise BaselRc5InputError(f"{feature} must be finite")

            minimum, maximum = self._feature_ranges[feature]
            if numeric < minimum or numeric > maximum:
                raise BaselRc5InputError(
                    f"{feature}={numeric} outside validated Basel rc5 domain [{minimum}, {maximum}]"
                )
            values[feature] = numeric
        return values

    def _resolve_unit_costs(
        self,
        *,
        water_unit_cost_chf_m3: float | None,
        whitening_unit_cost_chf_m2: float | None,
    ) -> dict[str, float]:
        values = {
            "water_unit_cost_chf_m3": (
                self.cost_defaults["water_unit_cost_chf_m3"]["value"]
                if water_unit_cost_chf_m3 is None
                else water_unit_cost_chf_m3
            ),
            "whitening_unit_cost_chf_m2": (
                self.cost_defaults["whitening_unit_cost_chf_m2"]["value"]
                if whitening_unit_cost_chf_m2 is None
                else whitening_unit_cost_chf_m2
            ),
        }
        for name, value in values.items():
            try:
                numeric = float(value)
            except (TypeError, ValueError) as exc:
                raise BaselRc5InputError(f"{name} must be numeric") from exc
            if math.isnan(numeric) or math.isinf(numeric):
                raise BaselRc5InputError(f"{name} must be finite")
            if numeric < 0:
                raise BaselRc5InputError(f"{name} must be non-negative")
            values[name] = numeric
        return values

    @staticmethod
    def _is_canonical_baseline(features: dict[str, float], *, cm3_enabled: bool) -> bool:
        return (
            not cm3_enabled
            and features["grass_irrfrac"] == 0.0
            and features["paved_albedo"] == 0.1
        )

    def _metadata(self, *, is_canonical_basel_baseline: bool) -> RuntimeMetadata:
        return RuntimeMetadata(
            city=self.manifest["bundle"]["city"],
            bundle_version=self.manifest["bundle"]["version"],
            model_version=self.manifest["bundle"]["version"],
            source_run=self.manifest["bundle"]["source_run"],
            training_context_id=self.training_context["context_id"],
            basel_only_validity=BASEL_ONLY_VALIDITY,
            applicability_statement=self.manifest["applicability"]["statement"],
            cost_assumption_status="illustrative user-configurable assumption",
            is_canonical_basel_baseline=is_canonical_basel_baseline,
            financial_assumption_statuses=dict(
                self.manifest["operational_financial"]["assumption_statuses"]
            ),
        )
