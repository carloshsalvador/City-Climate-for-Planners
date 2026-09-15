"""Portable application contract for dynamic SUEWS site-context results."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar, Protocol


CONTRACT_VERSION = "site_context_app_v1"


@dataclass(frozen=True)
class SiteContextRequest:
    """Framework-independent request for technical site-context evaluation."""

    latitude: float
    longitude: float
    radius_meter: float
    mode: str = "bbox"
    fallback_mode: str = "bbox"
    include_admin: bool = False
    include_lcz: bool = False
    admin_preferred_levels: tuple[str, ...] = ("ADM3", "ADM2", "ADM1", "ADM0")
    nearest_tolerance_km: float = 10.0


@dataclass(frozen=True)
class CapabilityStatus:
    """Status and message for one application-facing capability."""

    VALID_STATUSES: ClassVar[frozenset[str]] = frozenset(
        {"available", "partial", "preliminary", "unavailable", "failed"}
    )

    status: str
    message: str | None = None

    def __post_init__(self) -> None:
        if self.status not in self.VALID_STATUSES:
            expected = ", ".join(sorted(self.VALID_STATUSES))
            raise ValueError(
                f"Invalid SiteContext capability status {self.status!r}. "
                f"Expected one of: {expected}."
            )


@dataclass(frozen=True)
class SiteContextResult:
    """Serializable dynamic site-context result consumed by application code."""

    metadata: dict[str, Any]
    input: dict[str, Any]
    geometry: dict[str, Any]
    administrative_context: dict[str, Any]
    area: dict[str, Any]
    lcz: dict[str, Any]
    suews_fractions: dict[str, Any]
    site_properties: dict[str, Any]
    capabilities: dict[str, CapabilityStatus]
    provenance: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible dictionary without framework objects."""
        return _to_json_compatible(asdict(self))


class AdministrativeBoundaryProvider(Protocol):
    """Provider boundary for administrative context resolution."""

    def get_admin_info(self) -> dict[str, Any]:
        """Return canonical administrative information for a site."""


class LCZProvider(Protocol):
    """Provider boundary for LCZ source resolution."""

    def get_lcz(self, **kwargs: Any) -> dict[str, Any]:
        """Return LCZ extraction and summary data."""


class SitePropertyProvider(Protocol):
    """Provider boundary for optional site-property enrichment."""

    def get_site_properties_for_suews(self, **kwargs: Any) -> dict[str, Any]:
        """Return SUEWS-ready site properties with provenance."""


def build_result_metadata(
    *,
    adapter_name: str,
    generated_at_utc: datetime | None = None,
) -> dict[str, Any]:
    """Build standard contract metadata."""
    generated = generated_at_utc or datetime.now(timezone.utc)
    return {
        "contract_version": CONTRACT_VERSION,
        "adapter": adapter_name,
        "generated_at_utc": generated.isoformat(),
    }


def capability(status: str, message: str | None = None) -> CapabilityStatus:
    """Small helper to keep capability records consistent."""
    return CapabilityStatus(status=status, message=message)


def _to_json_compatible(value: Any) -> Any:
    if is_dataclass(value):
        return _to_json_compatible(asdict(value))
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _to_json_compatible(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_json_compatible(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return value.name
    if hasattr(value, "item"):
        try:
            return _to_json_compatible(value.item())
        except (AttributeError, TypeError, ValueError) as exc:
            raise TypeError(
                "Unsupported SiteContext contract NumPy-scalar-like value type: "
                f"{type(value).__name__}"
            ) from exc
    raise TypeError(
        f"Unsupported SiteContext contract value type: {type(value).__name__}"
    )
