"""Typed data passed between graph nodes.

Graph-based ADK workflows hand a node's typed return value to the next node.
HealthReport is the structured payload the deterministic `fetch_health` node
produces and the `report` LLM node consumes (via input_schema).
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
