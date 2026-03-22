from __future__ import annotations

import os

from celery import Celery


CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)

celery_app = Celery(
    "aura_travel_ai",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["app.infrastructure.tasks.disruption_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_ignore_result=True,
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.infrastructure.tasks.disruption_tasks.run_disruption_autopilot": {"queue": "autopilot"},
        "app.infrastructure.tasks.disruption_tasks.scan_active_trips": {"queue": "autopilot"},
    },
)
