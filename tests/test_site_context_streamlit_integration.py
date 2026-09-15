from pathlib import Path

import pytest

from app.frontend.site_context_controls import (
    build_site_context_request,
    capability_display,
    evaluated_result_state,
    format_area_km2,
    format_area_m2,
    site_context_request_identity,
    site_context_summary,
)
from app.runtime import BaselRc5Runtime
from app.site_context import SiteContextRequest, SiteContextRuntime
from app.site_context.contract import capability


FRONTEND_DIR = Path(__file__).resolve().parents[1] / "app" / "frontend"
TECHNICAL_SITE_PAGE = FRONTEND_DIR / "pages" / "02_technical_site.py"
SCENARIO_PAGE = FRONTEND_DIR / "pages" / "01_scenario.py"


def test_site_context_form_values_build_expected_request():
    request = build_site_context_request(
        latitude=47.5596,
        longitude=7.5886,
        radius_meter=5000,
        mode="bbox",
    )

    assert request == SiteContextRequest(
        latitude=47.5596,
        longitude=7.5886,
        radius_meter=5000.0,
        mode="bbox",
        fallback_mode="bbox",
        include_admin=False,
        include_lcz=False,
    )


def test_request_identity_is_derived_from_submitted_request():
    submitted_request = build_site_context_request(
        latitude=47.5596,
        longitude=7.5886,
        radius_meter=5000,
        mode="bbox",
        include_lcz=True,
    )

    assert site_context_request_identity(submitted_request) == {
        "latitude": 47.5596,
        "longitude": 7.5886,
        "radius_meter": 5000.0,
        "requested_mode": "bbox",
        "fallback_mode": "bbox",
        "include_admin": False,
        "include_lcz": True,
    }


def test_empty_evaluated_state_does_not_require_runtime_evaluation():
    state = evaluated_result_state(result=None, evaluated_request=None)

    assert state == {
        "has_evaluation": False,
        "serialized": None,
        "summary": None,
        "evaluated_request": None,
    }


def test_evaluated_state_preserves_submitted_request_identity():
    submitted_request = build_site_context_request(
        latitude=47.5596,
        longitude=7.5886,
        radius_meter=5000,
        mode="bbox",
    )
    result = SiteContextRuntime().evaluate(submitted_request)
    state = evaluated_result_state(
        result=result,
        evaluated_request=site_context_request_identity(submitted_request),
    )

    assert state["has_evaluation"] is True
    assert state["evaluated_request"]["latitude"] == 47.5596
    assert state["evaluated_request"]["radius_meter"] == 5000.0
    assert state["summary"]["surfacearea_m2"] == state["serialized"]["area"][
        "surfacearea_m2_for_config"
    ]


def test_failed_new_evaluation_replaces_previous_success_state():
    successful_request = build_site_context_request(
        latitude=47.5596,
        longitude=7.5886,
        radius_meter=5000,
        mode="bbox",
    )
    failed_request = build_site_context_request(
        latitude=85.0,
        longitude=7.5886,
        radius_meter=5000,
        mode="bbox",
    )
    runtime = SiteContextRuntime()
    success_state = evaluated_result_state(
        result=runtime.evaluate(successful_request),
        evaluated_request=site_context_request_identity(successful_request),
    )
    failed_state = evaluated_result_state(
        result=runtime.evaluate(failed_request),
        evaluated_request=site_context_request_identity(failed_request),
    )

    assert success_state["serialized"]["capabilities"]["geometry"]["status"] == "available"
    assert failed_state["evaluated_request"]["latitude"] == 85.0
    assert failed_state["serialized"]["capabilities"]["geometry"]["status"] == "failed"
    assert failed_state["serialized"]["geometry"] == {}


@pytest.mark.parametrize("mode", ["bbox", "buffer"])
def test_site_context_runtime_integration_for_ui_modes(mode):
    request = build_site_context_request(
        latitude=47.5596,
        longitude=7.5886,
        radius_meter=5000,
        mode=mode,
    )
    result = SiteContextRuntime().evaluate(request)
    summary = site_context_summary(result)

    assert summary["requested_mode"] == mode
    assert summary["effective_mode"] == mode
    assert summary["geometry_status"] == "available"
    assert summary["surfacearea_m2"] > 0


def test_validation_failure_can_be_serialized_for_presentation():
    result = SiteContextRuntime().evaluate(
        SiteContextRequest(latitude=85.0, longitude=7.5886, radius_meter=5000)
    )
    serialized = result.to_dict()

    assert serialized["capabilities"]["geometry"]["status"] == "failed"
    assert serialized["errors"][0]["type"] == "validation_error"


@pytest.mark.parametrize(
    "status",
    ["available", "partial", "preliminary", "unavailable", "failed"],
)
def test_capability_rendering_preserves_closed_status_vocabulary(status):
    display = capability_display(capability(status, "message"))

    assert display["status"] == status
    assert display["label"]
    assert display["message"] == "message"


def test_capability_rendering_rejects_unsupported_status():
    with pytest.raises(ValueError):
        capability_display({"status": "pending", "message": "not allowed"})


def test_lcz_unavailable_status_is_preserved_for_technical_page():
    request = build_site_context_request(
        latitude=47.5596,
        longitude=7.5886,
        radius_meter=5000,
        mode="bbox",
        include_lcz=True,
    )
    serialized = SiteContextRuntime().evaluate(request).to_dict()

    assert serialized["lcz"] == {}
    assert serialized["capabilities"]["lcz"]["status"] == "unavailable"


def test_technical_summary_consumes_serializable_site_context_result():
    result = SiteContextRuntime().evaluate(
        build_site_context_request(
            latitude=47.5596,
            longitude=7.5886,
            radius_meter=5000,
            mode="bbox",
        )
    )

    summary = site_context_summary(result)
    serialized = result.to_dict()

    assert summary["surfacearea_m2"] == serialized["area"]["surfacearea_m2_for_config"]
    assert summary["site_properties"]["surfacearea"] == summary["surfacearea_m2"]
    assert format_area_m2(summary["surfacearea_m2"]).endswith("m²")
    assert format_area_km2(summary["surfacearea_m2"]).endswith("km²")


def test_dynamic_site_context_changes_do_not_change_basel_outputs():
    basel_runtime = BaselRc5Runtime()
    baseline = basel_runtime.evaluate(
        grass_irrfrac=0.3,
        paved_albedo=0.4,
        cm3_enabled=True,
    ).to_dict()

    first_site = SiteContextRuntime().evaluate(
        build_site_context_request(
            latitude=47.5596,
            longitude=7.5886,
            radius_meter=1000,
            mode="bbox",
        )
    ).to_dict()
    second_site = SiteContextRuntime().evaluate(
        build_site_context_request(
            latitude=46.948,
            longitude=7.4474,
            radius_meter=8000,
            mode="buffer",
        )
    ).to_dict()
    repeated = basel_runtime.evaluate(
        grass_irrfrac=0.3,
        paved_albedo=0.4,
        cm3_enabled=True,
    ).to_dict()

    assert first_site["area"]["surfacearea_m2_for_config"] != second_site["area"][
        "surfacearea_m2_for_config"
    ]
    assert repeated == baseline


def test_technical_site_page_uses_runtime_boundary_without_geometry_algorithms():
    source = TECHNICAL_SITE_PAGE.read_text(encoding="utf-8")

    assert "SiteContextRuntime" in source
    assert "build_site_context_request" in source
    assert ".evaluate(" in source
    assert "shapely" not in source
    assert "pyproj" not in source
    assert "Transformer" not in source
    assert "buffer(" not in source
    assert "surfacearea_m2_for_config\"] /" not in source
    assert "BaselRc5Runtime" not in source
    assert "include_admin=True" not in source
    assert "default_request" not in source
    assert ".evaluate(default" not in source
    assert "site_context_evaluated_request" in source
    assert "Last Evaluated Request" in source
    assert "select \"Evaluate site\"" in source


def test_scenario_page_does_not_import_site_context_runtime():
    source = SCENARIO_PAGE.read_text(encoding="utf-8")

    assert "SiteContextRuntime" not in source
    assert "SiteContextRequest" not in source
    assert "surfacearea_m2_for_config" not in source
