"""Structured schemas for Nimbus.

The module is here to follow the agent template module organization.
`HealthReport` is a typed health snapshot for one service, available for
nodes that want typed output. The graph in this lab answers free-form. The
schemas stay local to keep Agent Engine deployment simple.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthReport(BaseModel):
    """Structured health snapshot for one service."""

    service: str
    known: bool = Field(
        description="False if the service name was not recognized.",
    )
    status: str = ""
    error_rate_pct: float = 0.0
    severity: str = ""
    p95_latency_ms: int = 0
    owner_team: str = ""
    last_deploy: str = ""
    note: str = Field(
        default="",
        description="Extra context, e.g. the known-services list when unknown.",
    )
