from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from typing import Any

from pyproj import CRS, Transformer
from shapely.geometry import Point, box, mapping
from shapely.ops import transform

from .contract import SiteContextRequest, SiteContextResult, build_result_metadata, capability


SUPPORTED_GEOMETRY_MODES = frozenset({"bbox", "buffer", "admin"})
LOCAL_FALLBACK_MODES = frozenset({"bbox", "buffer"})
WGS84_CRS = "EPSG:4326"


class SiteContextInputError(ValueError):
    """Raised when a SiteContext request cannot be evaluated."""


@dataclass(frozen=True)
class ResolvedGeometry:
    """Single source of truth for all geometry-derived outputs in one evaluation."""

    requested_mode: str
    effective_mode: str
    fallback_used: bool
    fallback_reason: str | None
    requested_geometry_available: bool
    point_geojson: dict[str, Any]
    effective_geometry_geojson: dict[str, Any]
    area_m2: float
    metric_crs: str
    radius_semantics: str


class SiteContextRuntime:
    """Public-safe dynamic SiteContext runtime for geometry-only M5C2 capabilities."""

    adapter_name = "SiteContextRuntime"

    def evaluate(self, request: SiteContextRequest) -> SiteContextResult:
        try:
            self._validate_request(request)
            resolved = self._resolve_geometry(request)
            return self._success_result(request, resolved)
        except SiteContextInputError as exc:
            return self._failure_result(request, str(exc))

    def _validate_request(self, request: SiteContextRequest) -> None:
        self._validate_finite("latitude", request.latitude)
        self._validate_finite("longitude", request.longitude)
        self._validate_finite("radius_meter", request.radius_meter)

        if not -90.0 <= float(request.latitude) <= 90.0:
            raise SiteContextInputError("latitude must be between -90 and 90 degrees")
        if not -180.0 <= float(request.longitude) <= 180.0:
            raise SiteContextInputError("longitude must be between -180 and 180 degrees")
        if float(request.radius_meter) <= 0:
            raise SiteContextInputError("radius_meter must be greater than 0")
        if request.mode not in SUPPORTED_GEOMETRY_MODES:
            raise SiteContextInputError(f"Unsupported geometry mode: {request.mode!r}")
        if request.mode == "admin" and request.fallback_mode not in LOCAL_FALLBACK_MODES:
            raise SiteContextInputError(
                "admin mode requires fallback_mode to be 'bbox' or 'buffer' in M5C2"
            )
        if request.mode != "admin" and request.fallback_mode not in SUPPORTED_GEOMETRY_MODES:
            raise SiteContextInputError(f"Unsupported fallback mode: {request.fallback_mode!r}")

    @staticmethod
    def _validate_finite(name: str, value: float) -> None:
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise SiteContextInputError(f"{name} must be numeric") from exc
        if math.isnan(numeric) or math.isinf(numeric):
            raise SiteContextInputError(f"{name} must be finite")

    def _resolve_geometry(self, request: SiteContextRequest) -> ResolvedGeometry:
        requested_mode = request.mode
        effective_mode = request.mode
        fallback_used = False
        fallback_reason = None
        requested_geometry_available = True

        if request.mode == "admin":
            effective_mode = request.fallback_mode
            fallback_used = True
            requested_geometry_available = False
            fallback_reason = (
                "Administrative-boundary resolution is not implemented in the public M5C2 "
                "provider set."
            )

        metric_crs = _utm_crs_for_location(request.latitude, request.longitude)
        transformer_to_metric = Transformer.from_crs(WGS84_CRS, metric_crs, always_xy=True)
        transformer_to_wgs84 = Transformer.from_crs(metric_crs, WGS84_CRS, always_xy=True)

        if effective_mode == "bbox":
            geometry_wgs84 = _bbox_geometry_wgs84(
                latitude=request.latitude,
                longitude=request.longitude,
                radius_meter=request.radius_meter,
            )
            geometry_metric = transform(transformer_to_metric.transform, geometry_wgs84)
            radius_semantics = "radius_meter is the square half-size in metres."
        elif effective_mode == "buffer":
            point_metric = transform(
                transformer_to_metric.transform,
                Point(request.longitude, request.latitude),
            )
            geometry_metric = point_metric.buffer(float(request.radius_meter))
            geometry_wgs84 = transform(transformer_to_wgs84.transform, geometry_metric)
            radius_semantics = "radius_meter is the true metric radial distance in metres."
        else:
            raise SiteContextInputError(f"Unsupported effective geometry mode: {effective_mode!r}")

        geojson = mapping(geometry_wgs84)
        if request.mode == "admin":
            radius_semantics = (
                "radius_meter does not define the requested administrative polygon; it is "
                f"used only for the local {effective_mode!r} fallback geometry."
            )

        return ResolvedGeometry(
            requested_mode=requested_mode,
            effective_mode=effective_mode,
            fallback_used=fallback_used,
            fallback_reason=fallback_reason,
            requested_geometry_available=requested_geometry_available,
            point_geojson={"type": "Point", "coordinates": [request.longitude, request.latitude]},
            effective_geometry_geojson=geojson,
            area_m2=float(geometry_metric.area),
            metric_crs=metric_crs.to_string(),
            radius_semantics=radius_semantics,
        )

    def _success_result(self, request: SiteContextRequest, resolved: ResolvedGeometry) -> SiteContextResult:
        warnings = []
        if resolved.fallback_used:
            warnings.append(f"Falling back to {resolved.effective_mode!r}: {resolved.fallback_reason}")
        if request.include_lcz:
            warnings.append("LCZ was requested, but no public LCZ provider is configured.")

        return SiteContextResult(
            metadata=build_result_metadata(
                adapter_name=self.adapter_name,
                generated_at_utc=datetime.now(timezone.utc),
            ),
            input=_input_section(request),
            geometry=_geometry_section(request, resolved),
            administrative_context=_admin_section(request, resolved),
            area=_area_section(resolved),
            lcz={},
            suews_fractions={},
            site_properties=_site_properties_section(request, resolved),
            capabilities=_capabilities_section(request, resolved),
            provenance=_provenance_section(),
            warnings=warnings,
            errors=[],
        )

    def _failure_result(self, request: SiteContextRequest, message: str) -> SiteContextResult:
        return SiteContextResult(
            metadata=build_result_metadata(adapter_name=self.adapter_name),
            input=_input_section(request),
            geometry={},
            administrative_context={},
            area={},
            lcz={},
            suews_fractions={},
            site_properties={},
            capabilities={
                "geometry": capability("failed", message),
                "admin": capability("unavailable", "Administrative lookup is not implemented."),
                "lcz": capability("unavailable", "LCZ resolution is not available."),
                "suews_fractions": capability(
                    "unavailable", "SUEWS fractions require a resolved LCZ source."
                ),
                "site_properties": capability("unavailable", "Geometry resolution failed."),
            },
            provenance=_provenance_section(),
            warnings=[],
            errors=[{"type": "validation_error", "message": message}],
        )


def _utm_crs_for_location(latitude: float, longitude: float) -> CRS:
    if not -80.0 <= float(latitude) <= 84.0:
        raise SiteContextInputError(
            "UTM metric CRS selection is supported only between 80S and 84N in M5C2"
        )
    zone = int((float(longitude) + 180.0) // 6.0) + 1
    zone = max(1, min(zone, 60))
    epsg = (32600 if latitude >= 0 else 32700) + zone
    return CRS.from_epsg(epsg)


def _bbox_geometry_wgs84(*, latitude: float, longitude: float, radius_meter: float):
    metres_per_degree = 111_320.0
    lat_delta = float(radius_meter) / metres_per_degree
    lon_delta = float(radius_meter) / (metres_per_degree * math.cos(math.radians(float(latitude))))
    return box(
        float(longitude) - lon_delta,
        float(latitude) - lat_delta,
        float(longitude) + lon_delta,
        float(latitude) + lat_delta,
    )


def _input_section(request: SiteContextRequest) -> dict[str, Any]:
    return {
        "latitude": request.latitude,
        "longitude": request.longitude,
        "radius_meter": request.radius_meter,
        "radius_unit": "m",
        "requested_mode": request.mode,
        "fallback_mode": request.fallback_mode,
        "include_admin": request.include_admin,
        "include_lcz": request.include_lcz,
    }


def _geometry_section(request: SiteContextRequest, resolved: ResolvedGeometry) -> dict[str, Any]:
    requested_geometry = (
        None if not resolved.requested_geometry_available else resolved.effective_geometry_geojson
    )
    return {
        "crs": WGS84_CRS,
        "effective_geometry_crs": WGS84_CRS,
        "point_geojson": resolved.point_geojson,
        "requested_mode": resolved.requested_mode,
        "effective_mode": resolved.effective_mode,
        "fallback_used": resolved.fallback_used,
        "fallback_reason": resolved.fallback_reason,
        "requested_matches_effective": resolved.requested_mode == resolved.effective_mode,
        "requested_geometry_available": resolved.requested_geometry_available,
        "requested_geometry_geojson": requested_geometry,
        "effective_geometry_geojson": resolved.effective_geometry_geojson,
        "radius_meter": float(request.radius_meter),
        "radius_semantics": resolved.radius_semantics,
    }


def _admin_section(request: SiteContextRequest, resolved: ResolvedGeometry) -> dict[str, Any]:
    status = "not_requested" if not request.include_admin and request.mode != "admin" else "unavailable"
    error = resolved.fallback_reason if request.mode == "admin" else None
    return {
        "status": status,
        "name": None,
        "admin_level": None,
        "country": None,
        "country_iso3": None,
        "polygon_geojson": None,
        "source": None,
        "error": error,
        "metadata": {},
    }


def _area_section(resolved: ResolvedGeometry) -> dict[str, Any]:
    requested_area = None if not resolved.requested_geometry_available else resolved.area_m2
    return {
        "requested_mode": resolved.requested_mode,
        "effective_mode": resolved.effective_mode,
        "fallback_used": resolved.fallback_used,
        "fallback_reason": resolved.fallback_reason,
        "requested_matches_effective": resolved.requested_mode == resolved.effective_mode,
        "requested_area_m2": requested_area,
        "surfacearea_m2_for_config": resolved.area_m2,
        "metric_crs_for_area": resolved.metric_crs,
        "area_unit": "m2",
        "warnings": [],
    }


def _site_properties_section(request: SiteContextRequest, resolved: ResolvedGeometry) -> dict[str, Any]:
    return {
        "values": {
            "lat": request.latitude,
            "lng": request.longitude,
            "surfacearea": resolved.area_m2,
        },
        "units": {
            "lat": "degrees",
            "lng": "degrees",
            "surfacearea": "m2",
        },
        "provenance": {
            "lat": {"source": "SiteContextRequest", "confidence": "high"},
            "lng": {"source": "SiteContextRequest", "confidence": "high"},
            "surfacearea": {
                "source": "SiteContextRuntime resolved geometry",
                "confidence": "high",
                "metric_crs_for_area": resolved.metric_crs,
            },
        },
        "warnings": [],
    }


def _capabilities_section(
    request: SiteContextRequest, resolved: ResolvedGeometry
) -> dict[str, Any]:
    if request.mode == "admin":
        admin_message = resolved.fallback_reason
    elif request.include_admin:
        admin_message = (
            "Administrative lookup was requested, but no public administrative provider is "
            "configured."
        )
    else:
        admin_message = "Administrative lookup was not requested."
    lcz_message = (
        "LCZ was requested, but no public LCZ provider is configured."
        if request.include_lcz
        else "LCZ resolution was not requested."
    )
    return {
        "geometry": capability("available"),
        "admin": capability("unavailable", admin_message),
        "lcz": capability("unavailable", lcz_message),
        "suews_fractions": capability(
            "unavailable", "SUEWS fractions require a resolved LCZ source."
        ),
        "site_properties": capability(
            "partial", "Only request and geometry-derived public properties are available."
        ),
    }


def _provenance_section() -> dict[str, Any]:
    return {
        "site_context_runtime": "app.site_context.runtime.SiteContextRuntime",
        "geometry_source": "public shapely/pyproj metric geometry runtime",
        "area_source": "single resolved metric geometry area",
        "admin_source": None,
        "lcz_source": None,
        "suews_fraction_source": None,
        "site_property_source": "request and resolved geometry",
        "fixed_surrogate_runtime_dependency": False,
        "dec_0024_boundary": (
            "Dynamic site-context outputs are not inputs to Basel rc5 surrogate inference."
        ),
    }
