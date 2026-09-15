from __future__ import annotations

from typing import Any

from app.site_context import CapabilityStatus, SiteContextRequest, SiteContextResult


GEOMETRY_MODE_OPTIONS = ("bbox", "buffer")
DEFAULT_LATITUDE = 47.5596
DEFAULT_LONGITUDE = 7.5886
DEFAULT_RADIUS_METER = 5000.0

CAPABILITY_LABELS = {
    "available": "Available",
    "partial": "Partial",
    "preliminary": "Preliminary",
    "unavailable": "Unavailable",
    "failed": "Failed",
}


def build_site_context_request(
    *,
    latitude: float,
    longitude: float,
    radius_meter: float,
    mode: str,
    include_lcz: bool = False,
) -> SiteContextRequest:
    return SiteContextRequest(
        latitude=float(latitude),
        longitude=float(longitude),
        radius_meter=float(radius_meter),
        mode=mode,
        fallback_mode="bbox",
        include_admin=False,
        include_lcz=include_lcz,
    )


def site_context_request_identity(request: SiteContextRequest) -> dict[str, Any]:
    return {
        "latitude": request.latitude,
        "longitude": request.longitude,
        "radius_meter": request.radius_meter,
        "requested_mode": request.mode,
        "fallback_mode": request.fallback_mode,
        "include_admin": request.include_admin,
        "include_lcz": request.include_lcz,
    }


def format_area_m2(value: float) -> str:
    return f"{value:,.0f} m²"


def format_area_km2(value: float) -> str:
    return f"{value / 1_000_000.0:,.3f} km²"


def capability_display(capability: CapabilityStatus | dict[str, Any]) -> dict[str, str | None]:
    if isinstance(capability, CapabilityStatus):
        status = capability.status
        message = capability.message
    else:
        status = str(capability["status"])
        message = capability.get("message")
    if status not in CapabilityStatus.VALID_STATUSES:
        raise ValueError(f"Unsupported SiteContext capability status: {status!r}")
    return {
        "label": CAPABILITY_LABELS[status],
        "status": status,
        "message": message,
    }


def site_context_summary(result: SiteContextResult) -> dict[str, Any]:
    serialized = result.to_dict()
    geometry = serialized.get("geometry", {})
    area = serialized.get("area", {})
    site_properties = serialized.get("site_properties", {}).get("values", {})
    return {
        "latitude": serialized["input"]["latitude"],
        "longitude": serialized["input"]["longitude"],
        "radius_meter": serialized["input"]["radius_meter"],
        "requested_mode": serialized["input"]["requested_mode"],
        "effective_mode": geometry.get("effective_mode"),
        "geometry_status": serialized["capabilities"]["geometry"]["status"],
        "output_crs": geometry.get("effective_geometry_crs"),
        "fallback_used": geometry.get("fallback_used"),
        "requested_matches_effective": geometry.get("requested_matches_effective"),
        "surfacearea_m2": area.get("surfacearea_m2_for_config"),
        "area_unit": area.get("area_unit"),
        "metric_crs": area.get("metric_crs_for_area"),
        "site_properties": {
            key: site_properties[key]
            for key in ("lat", "lng", "surfacearea")
            if key in site_properties
        },
    }


def evaluated_result_state(
    *,
    result: SiteContextResult | None,
    evaluated_request: dict[str, Any] | None,
) -> dict[str, Any]:
    if result is None or evaluated_request is None:
        return {
            "has_evaluation": False,
            "serialized": None,
            "summary": None,
            "evaluated_request": None,
        }
    return {
        "has_evaluation": True,
        "serialized": result.to_dict(),
        "summary": site_context_summary(result),
        "evaluated_request": dict(evaluated_request),
    }
