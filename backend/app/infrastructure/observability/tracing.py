from __future__ import annotations

import os


def init_tracing(service_name: str = "aura-travel-ai") -> None:
    """Best-effort OpenTelemetry bootstrap.

    If optional dependencies are not installed, service continues without tracing.
    """

    enabled = os.getenv("OTEL_ENABLED", "1").strip().lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    except Exception:
        return

    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: service_name}))
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)
