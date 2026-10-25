"""FastAPI app. Validates requests and reads pipeline artifacts - no ML logic."""
from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api import artifacts
from api.routers import actions, allocate, customers, home, insights, stats

log = logging.getLogger("api")


def _warm_curves() -> None:
    """Compute any missing or stale budget curves in the background, so the budget page never waits for them."""
    try:
        for strategy in ("segment_aware", "uniform", "risk_proportional"):
            allocate.allocate_curve(allocate.CurveRequest(strategy=strategy))
    except Exception:                       # warming is best effort; requests compute on demand
        log.exception("could not warm the budget curves")


@asynccontextmanager
async def lifespan(_: FastAPI):
    threading.Thread(target=_warm_curves, name="warm-curves", daemon=True).start()
    yield


app = FastAPI(title="Churn Predictor API", version="1.0.0", lifespan=lifespan)
app.include_router(customers.router, prefix="")
app.include_router(insights.router, prefix="")
app.include_router(allocate.router, prefix="")
app.include_router(home.router, prefix="")
app.include_router(stats.router, prefix="")
app.include_router(actions.router, prefix="")


@app.get("/health")
def health():
    try:
        artifacts._scores()
        return {"status": "ok", "artifacts_loaded": True}
    except FileNotFoundError:
        return {"status": "degraded", "artifacts_loaded": False}
