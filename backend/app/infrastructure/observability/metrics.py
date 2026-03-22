from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.responses import Response

HTTP_REQUESTS_TOTAL = Counter(
    "aura_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "aura_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path", "status"],
)

DISRUPTION_EVENTS_TOTAL = Counter(
    "aura_disruption_events_total",
    "Disruption analysis events",
    ["status"],
)

AUTOPILOT_REMEDIATIONS_TOTAL = Counter(
    "aura_autopilot_remediations_total",
    "Autopilot remediation outcomes",
    ["outcome"],
)


def observe_http_request(method: str, path: str, status: int, duration_seconds: float) -> None:
    status_text = str(status)
    HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status=status_text).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=path, status=status_text).observe(duration_seconds)


def mark_disruption_event(status: str) -> None:
    DISRUPTION_EVENTS_TOTAL.labels(status=status).inc()


def mark_autopilot_remediation(outcome: str) -> None:
    AUTOPILOT_REMEDIATIONS_TOTAL.labels(outcome=outcome).inc()


def metrics_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
