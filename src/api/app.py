"""FastAPI app. Validates requests and reads pipeline artifacts - no ML logic."""
from __future__ import annotations

from fastapi import FastAPI

from api import artifacts
from api.routers import allocate, customers, insights

app = FastAPI(title="Churn Predictor API", version="1.0.0")
app.include_router(customers.router, prefix="")
app.include_router(insights.router, prefix="")
app.include_router(allocate.router, prefix="")


@app.get("/health")
def health():
    try:
        artifacts._scores()
        return {"status": "ok", "artifacts_loaded": True}
    except FileNotFoundError:
        return {"status": "degraded", "artifacts_loaded": False}
