"""Cymbal ops tools served as an MCP server over Streamable HTTP.

This server wraps the ops tools in `tools.py` as MCP tools and serves them
over HTTP, so they can be deployed to Cloud Run, registered in Agent Registry
and consumed by any MCP client, including Nimbus through
`AgentRegistry.get_mcp_toolset`.

To run it locally, use `uvicorn server:app --port 8080` and connect to
http://localhost:8080/mcp. On Cloud Run the Dockerfile runs
`uvicorn server:app` on the port given by $PORT.

The server continues the caller's OpenTelemetry trace. It extracts the W3C
`traceparent` from the incoming request and emits a SERVER span to Cloud
Trace, together with a child `execute_tool` span for every tool call, so the
MCP spans land in the same trace as Nimbus's `invoke_workflow`. That shared
trace is what lets the Cloud Trace topology view draw the edge from nimbus
to cymbal-ops-mcp, because the graph is built from aggregated Cloud Trace data
and an edge only appears when the spans are correlated. Tracing is
best-effort. If the OpenTelemetry libraries are not installed, as in offline
unit tests, the server still runs.
"""

from __future__ import annotations

import contextlib
import json
import os
import warnings

warnings.filterwarnings(
    "ignore", message=r".*CloudTraceSpanExporter is deprecated.*"
)
from collections.abc import AsyncIterator, Iterator
from typing import Any

import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.types import Receive, Scope, Send

from tools import (
    get_error_rate,
    get_service_health,
    list_services,
)

SERVER_NAME = "cymbal-ops-mcp"

# OpenTelemetry tracing. It is optional and is enabled in the deployed
# container.
_TRACER: Any = None
# One-time startup diagnostic that records whether the caller propagated a
# _meta traceparent.
_DIAG: dict[str, bool] = {"done": False}


def _init_tracing() -> Any:
    """Configures a Cloud Trace exporter and returns a tracer.

    Uses the default W3C TraceContext propagator so an incoming `traceparent`
    parents our spans.

    Returns:
        An OpenTelemetry tracer for this server, or None if OTel isn't
        available or tracing is disabled via OTEL_TRACING.
    """
    if os.environ.get("OTEL_TRACING", "1") != "1":
        return None
    try:
        # Deferred: the OpenTelemetry stack only exists in the deployed
        # container.
        from opentelemetry import trace
        from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        return None
    project = os.environ.get("GOOGLE_CLOUD_PROJECT") or None
    base = Resource.create(
        {"service.name": SERVER_NAME, "gcp.mcp.server.id": SERVER_NAME}
    )
    # The GCP detector adds the Cloud Run attributes that let Cloud Trace link
    # these spans to the registered service node.
    resource = base
    try:
        from opentelemetry.resourcedetector.gcp_resource_detector import (
            GoogleCloudResourceDetector,
        )
        from opentelemetry.sdk.resources import get_aggregated_resources

        detected = get_aggregated_resources(
            [GoogleCloudResourceDetector(raise_on_error=False)]
        )
        # The `base` resource wins on overlap, which keeps `service.name` set
        # to cymbal-ops-mcp.
        resource = detected.merge(base)
        if os.environ.get("OTEL_DEBUG"):
            print(f"[otel] resource attrs: {dict(resource.attributes)}", flush=True)
    except Exception as e:
        # Tracing is best effort, so fall back to the base resource when the
        # detector or the metadata server is unavailable.
        if os.environ.get("OTEL_DEBUG"):
            print(f"[otel] gcp resource detection skipped: {e}", flush=True)
    provider = TracerProvider(resource=resource)
    exporter = (
        CloudTraceSpanExporter(project_id=project)
        if project
        else CloudTraceSpanExporter()
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return trace.get_tracer(SERVER_NAME)


def _ctx_from_meta(meta: Any) -> Any:
    """Builds an OTel context from the MCP request `_meta.traceparent` (W3C).

    ADK injects the active trace context, which is the agent's
    `invoke_workflow` trace, into the MCP request's `_meta` field at call time
    (see `google.adk...mcp_tool.py`). It does not reliably inject it into the
    HTTP header, because that carrier comes from the client's connection task
    and starts a fresh trace. Reading `_meta` is also what Google's own MCP
    servers do, as described in the Cloud Trace guide
    monitor-mcp-tool-use-with-cloud-trace.

    Args:
        meta: The MCP request `_meta` object (opaque MCP type), or None.

    Returns:
        An OpenTelemetry context to parent our spans to, or None if no usable
        traceparent was propagated.
    """
    if meta is None:
        return None
    try:
        carrier: dict[str, str] = {}
        traceparent = getattr(meta, "traceparent", None)
        tracestate = getattr(meta, "tracestate", None)
        if traceparent is None and hasattr(meta, "model_dump"):
            # With extra="allow" the key lives in model_extra.
            dumped = meta.model_dump()
            traceparent = dumped.get("traceparent")
            tracestate = dumped.get("tracestate")
        if not traceparent:
            return None
        carrier["traceparent"] = traceparent
        if tracestate:
            carrier["tracestate"] = tracestate
        # This import is deferred because OpenTelemetry is optional, as
        # explained in _init_tracing.
        from opentelemetry.propagate import extract

        return extract(carrier)
    except Exception:
        # Trace propagation is best effort and must never break a tool call.
        return None


@contextlib.contextmanager
def _tool_span(name: str, meta: Any = None) -> Iterator[None]:
    """Opens a SERVER span for a single tool call.

    The span is parented to the caller's `_meta` trace so the MCP span joins
    Nimbus's `invoke_workflow` trace (that shared trace is what draws the same trace).

    Args:
        name: The MCP tool name being executed.
        meta: The MCP request `_meta` carrying the caller's traceparent, if any.

    Yields:
        None; the wrapped block runs inside the span (or unchanged when
        tracing is off).
    """
    if _TRACER is None:
        yield
        return
    # This import is deferred because OpenTelemetry is optional, as explained
    # in _init_tracing.
    from opentelemetry.trace import SpanKind

    # Parent the span to the agent's trace when one was propagated.
    ctx = _ctx_from_meta(meta)
    with _TRACER.start_as_current_span(
        f"execute_tool {name}", context=ctx, kind=SpanKind.SERVER
    ) as span:
        span.set_attribute("gen_ai.operation.name", "execute_tool")
        span.set_attribute("gen_ai.tool.name", name)
        span.set_attribute("mcp.method.name", "tools/call")
        span.set_attribute("gcp.mcp.server.id", SERVER_NAME)
        span.set_attribute("service.name", SERVER_NAME)
        yield


def build_mcp_server() -> Server:
    """Builds the MCP server that exposes the Cymbal ops tools over HTTP.

    Returns:
        A low-level MCP `Server` with the three ops tools registered.
    """
    server: Server = Server(SERVER_NAME)

    @server.list_tools()
    async def _list_tools() -> list[types.Tool]:
        """Advertises the tool catalogue to the connected MCP client."""
        return [
            types.Tool(
                name="list_services",
                description="List the Cymbal services you can observe.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
            types.Tool(
                name="get_service_health",
                description=(
                    "Get the current health summary for one Cymbal service."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "service": {
                            "type": "string",
                            "description": "service name, e.g. checkout",
                        },
                    },
                    "required": ["service"],
                },
            ),
            types.Tool(
                name="get_error_rate",
                description=(
                    "Get the error rate and severity for a service over a"
                    " time window."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "service": {
                            "type": "string",
                            "description": "service name, e.g. checkout",
                        },
                        "window": {
                            "type": "string",
                            "description": "look-back window, e.g. 1h",
                        },
                    },
                    "required": ["service"],
                },
            ),
        ]

    @server.call_tool()
    async def _call_tool(
        name: str, arguments: dict[str, Any]
    ) -> list[types.ContentBlock]:
        """Dispatches an MCP tool call to the local Python function."""
        meta = None
        try:
            # Carries ADK's injected _meta.traceparent.
            meta = server.request_context.meta
        except Exception:
            # The catch is broad on purpose. Outside a live request there is
            # no request_context, and tracing must never break a tool call.
            meta = None
        if not _DIAG["done"]:
            # Confirm once that the caller propagated a _meta traceparent.
            traceparent = (
                getattr(meta, "traceparent", None) if meta is not None else None
            )
            if os.environ.get("OTEL_DEBUG"):
                print(f"[otel] _meta.traceparent={traceparent!r}", flush=True)
            _DIAG["done"] = True
        with _tool_span(name, meta):
            if name == "list_services":
                result = list_services()
            elif name == "get_service_health":
                result = get_service_health(arguments.get("service", ""))
            elif name == "get_error_rate":
                result = get_error_rate(
                    arguments.get("service", ""),
                    arguments.get("window", "1h"),
                )
            else:
                raise ValueError(f"unknown tool: {name}")
        return [types.TextContent(type="text", text=json.dumps(result))]

    return server


def build_asgi_app() -> Starlette:
    """Builds the Starlette app that serves MCP over Streamable HTTP.

    Returns:
        A Starlette application mounting the MCP session manager at `/mcp`.
    """
    global _TRACER
    _TRACER = _init_tracing()
    server = build_mcp_server()
    # Setting stateless=True keeps it horizontally scalable on Cloud Run.
    session_manager = StreamableHTTPSessionManager(
        app=server, event_store=None, stateless=True
    )

    async def handle_mcp(scope: Scope, receive: Receive, send: Send) -> None:
        """Hands the ASGI request to the MCP Streamable HTTP manager."""
        # Parent the span to the request's `_meta.traceparent`. The HTTP header
        # one belongs to the connection task and starts a disconnected trace.
        await session_manager.handle_request(scope, receive, send)

    @contextlib.asynccontextmanager
    async def lifespan(_: Starlette) -> AsyncIterator[None]:
        """Runs the MCP session manager for the lifetime of the app."""
        async with session_manager.run():
            yield

    return Starlette(
        debug=False,
        routes=[Mount("/mcp", app=handle_mcp)],
        lifespan=lifespan,
    )


# The uvicorn entrypoint, started with `uvicorn server:app`.
app = build_asgi_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
