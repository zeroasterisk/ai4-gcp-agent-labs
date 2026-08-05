"""Ops tools for Nimbus, defined here in the MCP server.

The tools belong to the MCP server. It defines them and exposes them over MCP,
and the agent gets access only through MCP, never by importing these
functions. They are read-only and fixture-backed, so the agent stays
deterministic and testable offline. `server.py` wraps each one as an MCP tool.
"""

from __future__ import annotations

from typing import Any

# Fixture "fleet" for the fictional company Cymbal. The error_rate_pct value
# covers the last hour and p95_latency_ms is the current p95.
_SERVICES: dict[str, dict[str, Any]] = {
    "checkout": {
        "environment": "prod",
        "status": "degraded",
        "error_rate_pct": 4.7,
        "p95_latency_ms": 1830,
        "last_deploy": "2026-07-16T08:12:00Z",
        "owner_team": "payments-core",
    },
    "payments": {
        "environment": "prod",
        "status": "healthy",
        "error_rate_pct": 0.2,
        "p95_latency_ms": 240,
        "last_deploy": "2026-07-14T15:40:00Z",
        "owner_team": "payments-core",
    },
    "search": {
        "environment": "prod",
        "status": "healthy",
        "error_rate_pct": 0.5,
        "p95_latency_ms": 310,
        "last_deploy": "2026-07-15T11:05:00Z",
        "owner_team": "discovery",
    },
    "recommendations": {
        "environment": "prod",
        "status": "healthy",
        "error_rate_pct": 0.9,
        "p95_latency_ms": 520,
        "last_deploy": "2026-07-13T09:22:00Z",
        "owner_team": "discovery",
    },
}

# Severity thresholds for get_error_rate(), in percent.
_HIGH_ERROR_RATE_PCT: float = 2.0
_ELEVATED_ERROR_RATE_PCT: float = 1.0


def list_services() -> dict[str, list[str]]:
    """List the Cymbal services Nimbus can observe.

    Returns:
        A dict with the key "services" mapping to a list of known service
        names.
    """
    return {"services": sorted(_SERVICES.keys())}


def get_service_health(service: str) -> dict[str, Any]:
    """Get the current health summary for a single service.

    Args:
        service: The service name, e.g. "checkout". Case-insensitive.

    Returns:
        A dict with status, error_rate_pct, p95_latency_ms, last_deploy,
        owner_team and environment for the service, or an "error" key if the
        service is unknown.
    """
    key = (service or "").strip().lower()
    record = _SERVICES.get(key)
    if record is None:
        return {
            "error": f"unknown service '{service}'",
            "known_services": sorted(_SERVICES.keys()),
        }
    return {"service": key, **record}


def get_error_rate(service: str, window: str = "1h") -> dict[str, Any]:
    """Get the error rate for a service over a time window.

    Args:
        service: The service name, e.g. "checkout". Case-insensitive.
        window: The look-back window label, which is informational in this
          lab, default "1h".

    Returns:
        A dict with the service, window, error_rate_pct and a simple severity
        label, or an "error" key if the service is unknown.
    """
    key = (service or "").strip().lower()
    record = _SERVICES.get(key)
    if record is None:
        return {
            "error": f"unknown service '{service}'",
            "known_services": sorted(_SERVICES.keys()),
        }
    rate = record["error_rate_pct"]
    if rate >= _HIGH_ERROR_RATE_PCT:
        severity = "high"
    elif rate >= _ELEVATED_ERROR_RATE_PCT:
        severity = "elevated"
    else:
        severity = "normal"
    return {
        "service": key,
        "window": window,
        "error_rate_pct": rate,
        "severity": severity,
    }
