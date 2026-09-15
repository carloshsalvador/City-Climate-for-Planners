import ast
import hashlib
import json
from pathlib import Path

import pytest
from pyproj import Transformer
from shapely.geometry import Point, box, shape
from shapely.ops import transform

from app.site_context import CONTRACT_VERSION, SiteContextRequest, SiteContextRuntime


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = REPO_ROOT / "app" / "site_context" / "contract.py"
RUNTIME_PATH = REPO_ROOT / "app" / "site_context" / "runtime.py"
BASEL_RUNTIME_PATH = REPO_ROOT / "app" / "runtime" / "basel_rc5.py"
ARTIFACT_DIR = REPO_ROOT / "app" / "artifacts" / "site_context_app_v1"
GOLDEN_PATH = ARTIFACT_DIR / "validation" / "contract_golden.json"

CONTRACT_SHA256 = "1b62889d6f066e4b9d6fc6cf59edee6a12a1d4a65e9a0135c77e18f2e6cde455"
GOLDEN_SHA256 = "cabe8853ab4c171ed0a9b37875cf00c65ec295e4f8d6b24d202b66cc03230b12"

AREA_REL_TOL = 1e-3
POINT_ABS_TOL_DEG = 1e-9
BBOX_BOUNDS_ABS_TOL_DEG = 1e-12
BUFFER_BOUNDS_ABS_TOL_DEG = 2e-3
BBOX_AREA_REL_TOL = 1e-9

FORBIDDEN_SITE_CONTEXT_IMPORTS = {
    "SuewsSiteContext",
    "site_context.core",
    "project_config",
    "geopandas",
    "rasterio",
    "supy",
    "BaselRc5Runtime",
    "basel_rc5",
}
FORBIDDEN_SITE_CONTEXT_SOURCE_STRINGS = {
    "SuewsSiteContext",
    "site_context.core",
    "project_config",
    "geopandas",
    "rasterio",
    "supy",
    "BaselRc5Runtime",
    "basel_rc5",
}


@pytest.fixture(scope="module")
def golden() -> dict:
    with GOLDEN_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture(scope="module")
def runtime() -> SiteContextRuntime:
    return SiteContextRuntime()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _scenario(golden: dict, scenario_id: str) -> dict:
    return next(item for item in golden["scenarios"] if item["scenario_id"] == scenario_id)


def _request_from_scenario(scenario: dict) -> SiteContextRequest:
    return SiteContextRequest(**scenario["request"])


def test_promoted_artifact_hashes_and_manifest_identity():
    manifest = json.loads((ARTIFACT_DIR / "manifest.json").read_text(encoding="utf-8"))

    assert _sha256(CONTRACT_PATH) == CONTRACT_SHA256
    assert _sha256(GOLDEN_PATH) == GOLDEN_SHA256
    assert manifest["app_contract_sha256"] == CONTRACT_SHA256
    assert manifest["contract_golden_sha256"] == GOLDEN_SHA256
    assert manifest["contract_version"] == "site_context_app_v1"
    assert "contract and validation fixtures only" in manifest["package_statement"]
    assert manifest["included_files"]
    assert "BaselRc5Runtime and surrogate model artefacts" in manifest[
        "excluded_private_provider_components"
    ]
    assert CONTRACT_VERSION == "site_context_app_v1"


@pytest.mark.parametrize("scenario_id", ["bbox_geometry_only", "buffer_geometry_only"])
def test_basel_geometry_golden_subset_parity(runtime, golden, scenario_id):
    scenario = _scenario(golden, scenario_id)
    expected = scenario["expected"]
    actual = runtime.evaluate(_request_from_scenario(scenario)).to_dict()

    assert actual["geometry"]["effective_geometry_geojson"]["type"] == "Polygon"
    assert actual["geometry"]["requested_mode"] == expected["geometry"]["requested_mode"]
    assert actual["geometry"]["effective_mode"] == expected["geometry"]["effective_mode"]
    assert actual["geometry"]["fallback_used"] == expected["geometry"]["fallback_used"]
    assert actual["geometry"]["requested_matches_effective"] is True
    assert actual["geometry"]["requested_geometry_available"] is True
    assert actual["geometry"]["crs"] == "EPSG:4326"
    assert actual["geometry"]["effective_geometry_crs"] == "EPSG:4326"
    assert actual["area"]["metric_crs_for_area"] == "EPSG:32632"
    assert actual["area"]["area_unit"] == "m2"
    assert actual["capabilities"]["geometry"]["status"] == "available"

    actual_point = actual["geometry"]["point_geojson"]["coordinates"]
    expected_point = expected["geometry"]["point_geojson"]["coordinates"]
    assert actual_point[0] == pytest.approx(expected_point[0], abs=POINT_ABS_TOL_DEG)
    assert actual_point[1] == pytest.approx(expected_point[1], abs=POINT_ABS_TOL_DEG)
    actual_shape = shape(actual["geometry"]["effective_geometry_geojson"])
    expected_shape = shape(expected["geometry"]["effective_geometry_geojson"])
    assert actual_shape.is_valid
    bounds_tolerance = (
        BBOX_BOUNDS_ABS_TOL_DEG
        if scenario_id == "bbox_geometry_only"
        else BUFFER_BOUNDS_ABS_TOL_DEG
    )
    area_tolerance = BBOX_AREA_REL_TOL if scenario_id == "bbox_geometry_only" else AREA_REL_TOL
    assert actual["area"]["surfacearea_m2_for_config"] == pytest.approx(
        expected["area"]["surfacearea_m2_for_config"], rel=area_tolerance
    )
    for actual_bound, expected_bound in zip(actual_shape.bounds, expected_shape.bounds):
        assert actual_bound == pytest.approx(expected_bound, abs=bounds_tolerance)

    if scenario_id == "bbox_geometry_only":
        assert "half-size" in actual["geometry"]["radius_semantics"]
    else:
        assert "radial distance" in actual["geometry"]["radius_semantics"]


def test_bbox_bounds_are_canonical_epsg4326_not_utm_square(runtime, golden):
    scenario = _scenario(golden, "bbox_geometry_only")
    expected = shape(scenario["expected"]["geometry"]["effective_geometry_geojson"])
    actual = runtime.evaluate(_request_from_scenario(scenario)).to_dict()
    actual_shape = shape(actual["geometry"]["effective_geometry_geojson"])

    for actual_bound, expected_bound in zip(actual_shape.bounds, expected.bounds):
        assert actual_bound == pytest.approx(expected_bound, abs=BBOX_BOUNDS_ABS_TOL_DEG)

    metric_crs = actual["area"]["metric_crs_for_area"]
    to_metric = Transformer.from_crs("EPSG:4326", metric_crs, always_xy=True)
    to_wgs84 = Transformer.from_crs(metric_crs, "EPSG:4326", always_xy=True)
    point_metric = transform(
        to_metric.transform,
        Point(scenario["request"]["longitude"], scenario["request"]["latitude"]),
    )
    radius = scenario["request"]["radius_meter"]
    old_utm_square = transform(
        to_wgs84.transform,
        box(
            point_metric.x - radius,
            point_metric.y - radius,
            point_metric.x + radius,
            point_metric.y + radius,
        ),
    )

    with pytest.raises(AssertionError):
        for actual_bound, old_bound in zip(expected.bounds, old_utm_square.bounds):
            assert actual_bound == pytest.approx(old_bound, abs=BBOX_BOUNDS_ABS_TOL_DEG)


def test_lcz_unavailable_request_semantics(runtime, golden):
    scenario = _scenario(golden, "lcz_unavailable_request")
    actual = runtime.evaluate(_request_from_scenario(scenario)).to_dict()

    assert actual["lcz"] == {}
    assert actual["suews_fractions"] == {}
    assert actual["capabilities"]["lcz"]["status"] == "unavailable"
    assert "no public LCZ provider" in actual["capabilities"]["lcz"]["message"]
    assert actual["capabilities"]["suews_fractions"]["status"] == "unavailable"


def test_admin_falls_back_without_faking_admin_polygon(runtime):
    result = runtime.evaluate(
        SiteContextRequest(
            latitude=47.5596,
            longitude=7.5886,
            radius_meter=5000,
            mode="admin",
            fallback_mode="bbox",
            include_admin=True,
        )
    ).to_dict()

    assert result["geometry"]["requested_mode"] == "admin"
    assert result["geometry"]["effective_mode"] == "bbox"
    assert result["geometry"]["fallback_used"] is True
    assert result["geometry"]["requested_geometry_available"] is False
    assert result["administrative_context"]["polygon_geojson"] is None
    assert result["capabilities"]["admin"]["status"] == "unavailable"
    assert "does not define the requested administrative polygon" in result["geometry"][
        "radius_semantics"
    ]
    assert "fallback geometry" in result["geometry"]["radius_semantics"]


@pytest.mark.parametrize("mode", ["bbox", "buffer"])
def test_include_admin_true_has_explicit_unavailable_message(runtime, mode):
    result = runtime.evaluate(
        SiteContextRequest(
            latitude=47.5596,
            longitude=7.5886,
            radius_meter=5000,
            mode=mode,
            include_admin=True,
        )
    ).to_dict()

    assert result["capabilities"]["admin"]["status"] == "unavailable"
    assert result["capabilities"]["admin"]["message"] == (
        "Administrative lookup was requested, but no public administrative provider is configured."
    )


def test_invalid_geometry_request_returns_structured_failure(runtime):
    result = runtime.evaluate(
        SiteContextRequest(latitude=91.0, longitude=7.5886, radius_meter=5000)
    ).to_dict()

    assert result["capabilities"]["geometry"]["status"] == "failed"
    assert result["errors"][0]["type"] == "validation_error"
    assert result["geometry"] == {}


def test_one_effective_geometry_drives_area_and_site_properties(runtime):
    result = runtime.evaluate(
        SiteContextRequest(latitude=47.5596, longitude=7.5886, radius_meter=5000)
    ).to_dict()

    area = result["area"]["surfacearea_m2_for_config"]
    assert result["site_properties"]["values"]["surfacearea"] == area
    assert result["site_properties"]["provenance"]["surfacearea"]["metric_crs_for_area"] == result[
        "area"
    ]["metric_crs_for_area"]


def test_dynamic_utm_crs_selection(runtime):
    north = runtime.evaluate(
        SiteContextRequest(latitude=47.5596, longitude=7.5886, radius_meter=1000)
    ).to_dict()
    south = runtime.evaluate(
        SiteContextRequest(latitude=-33.86, longitude=151.2, radius_meter=1000)
    ).to_dict()

    assert north["area"]["metric_crs_for_area"] == "EPSG:32632"
    assert south["area"]["metric_crs_for_area"] == "EPSG:32756"


def test_public_site_context_runtime_has_no_private_or_basel_imports():
    source = RUNTIME_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_names.add(node.module)

    assert not (FORBIDDEN_SITE_CONTEXT_IMPORTS & imported_names)
    assert not any(name in source for name in FORBIDDEN_SITE_CONTEXT_SOURCE_STRINGS)


def test_basel_runtime_has_no_site_context_imports_or_dynamic_inputs():
    source = BASEL_RUNTIME_PATH.read_text(encoding="utf-8")

    assert "SiteContextRuntime" not in source
    assert "SiteContextRequest" not in source
    assert "dynamic area" not in source
    assert "dynamic geometry" not in source
    assert "dynamic lat" not in source
    assert "dynamic LCZ" not in source
