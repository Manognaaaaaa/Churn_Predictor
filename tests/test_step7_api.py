import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def client():
    subprocess.run([sys.executable, "scripts/make_mocks.py"], cwd=ROOT, check=True)
    sys.path.insert(0, str(ROOT / "src"))
    from api import artifacts
    artifacts.reset_cache()
    from api.app import app
    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_customers_list_and_detail(client):
    r = client.get("/customers", params={"limit": 5, "risk_band": "red"})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 0 and len(body["items"]) <= 5
    cid = body["items"][0]["customer_id"]
    d = client.get(f"/customers/{cid}")
    assert d.status_code == 200
    assert d.json()["customer_id"] == cid
    assert len(d.json()["top_drivers"]) == 5
    assert client.get("/customers/NOPE-404").status_code == 404


def test_portfolio_forecast_metrics(client):
    p = client.get("/portfolio/summary").json()
    assert {"n_customers", "total_revenue_at_risk", "band_counts", "by_segment"} <= set(p)
    f = client.get("/forecast", params={"scenario": "no_intervention"}).json()
    assert f["scenario"] == "no_intervention" and len(f["points"]) > 0
    m = client.get("/model/metrics").json()
    assert "models" in m and "calibration_curve" in m


def test_allocate_endpoint(client):
    r = client.post("/allocate", json={"budget": 20000, "strategy": "segment_aware"})
    assert r.status_code == 200
    body = r.json()
    assert body["budget"] == 20000
    assert body["spent"] <= 20000 + 1e-6
    assert body["expected_revenue_saved"] > 0
    assert len(body["allocations"]) > 0


def test_pdf_report(client):
    cid = client.get("/customers", params={"limit": 1}).json()["items"][0]["customer_id"]
    r = client.get(f"/customers/{cid}/report.pdf")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content[:5] == b"%PDF-"
