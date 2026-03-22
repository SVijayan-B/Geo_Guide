from __future__ import annotations

from fastapi import FastAPI

from app.api.modern_routes import router as modern_router
from app.config import APP_NAME
from app.db.database import Base, engine
from app.infrastructure.observability.logging import configure_logging
from app.infrastructure.observability.metrics import metrics_response
from app.infrastructure.observability.middleware import RequestContextMiddleware
from app.infrastructure.observability.tracing import init_tracing
from app.models import auth, autopilot, chat, trip, user
from app.routes import router as legacy_router

_ = (auth, autopilot, chat, trip, user)

configure_logging()
init_tracing(service_name="aura-travel-ai")

# Keep create_all for local/dev compatibility while Alembic handles prod migrations.
Base.metadata.create_all(bind=engine)

app = FastAPI(title=APP_NAME)
app.add_middleware(RequestContextMiddleware)

# Legacy endpoints are preserved.
app.include_router(legacy_router)
# Modern platform endpoints.
app.include_router(modern_router)


@app.get("/")
def root():
    return {"message": f"{APP_NAME} is live"}


@app.get("/metrics")
def metrics():
    return metrics_response()
