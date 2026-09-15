import json

import pytest

from app.site_context.contract import (
    CONTRACT_VERSION,
    CapabilityStatus,
    SiteContextRequest,
    SiteContextResult,
    capability,
)


EXPECTED_TOP_LEVEL_SECTIONS = {
    "metadata",
    "input",
    "geometry",
    "administrative_context",
    "area",
    "lcz",
    "suews_fractions",
    "site_properties",
    "capabilities",
    "provenance",
    "warnings",
    "errors",
}


def test_valid_site_context_request_creation():
    request = SiteContextRequest(latitude=47.5596, longitude=7.5886, radius_meter=5000)

    assert request.latitude == 47.5596
    assert request.longitude == 7.5886
    assert request.mode == "bbox"
    assert CONTRACT_VERSION == "site_context_app_v1"


@pytest.mark.parametrize(
    "status",
    ["available", "partial", "preliminary", "unavailable", "failed"],
)
def test_capability_status_accepts_closed_vocabulary(status):
    assert CapabilityStatus(status=status).status == status


def test_capability_status_rejects_unknown_value():
    with pytest.raises(ValueError):
        CapabilityStatus(status="pending")


def test_result_serializes_to_json_compatible_dict():
    result = SiteContextResult(
        metadata={"contract_version": CONTRACT_VERSION, "adapter": "test"},
        input={"latitude": 47.5596},
        geometry={"point_geojson": {"type": "Point", "coordinates": [7.5886, 47.5596]}},
        administrative_context={},
        area={"surfacearea_m2_for_config": 1.0},
        lcz={},
        suews_fractions={},
        site_properties={},
        capabilities={"geometry": capability("available")},
        provenance={},
    )

    serialized = result.to_dict()

    assert set(serialized) == EXPECTED_TOP_LEVEL_SECTIONS
    assert serialized["capabilities"]["geometry"]["status"] == "available"
    json.dumps(serialized)


def test_serializer_rejects_arbitrary_objects():
    result = SiteContextResult(
        metadata={"bad": object()},
        input={},
        geometry={},
        administrative_context={},
        area={},
        lcz={},
        suews_fractions={},
        site_properties={},
        capabilities={},
        provenance={},
    )

    with pytest.raises(TypeError):
        result.to_dict()
