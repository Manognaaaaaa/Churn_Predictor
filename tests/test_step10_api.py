"""Step 10 endpoints (mock-backed like the step 7 tests): customers, home rows, stats, allocation extras."""
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
    real = artifacts.artifacts_dir
    mock = ROOT / "artifacts" / "mock"
    artifacts.artifacts_dir = lambda: mock          # always test against the small mock set
    artifacts.reset_cache()
    from api.app import app
    yield TestClient(app)
    artifacts.artifacts_dir = real
    artifacts.reset_cache()


def test_list_has_raw_fields_filters_and_search(client):
    r = client.get("/customers", params={"limit": 500}).json()
    assert r["total"] == 200 and r["items"][0]["surname"]
    vals = [i["revenue_at_risk"] for i in r["items"]]
    assert vals == sorted(vals, reverse=True)
    de = client.get("/customers", params={"country": "Germany", "limit": 500}).json()
    assert de["total"] and all(i["geography"] == "Germany" for i in de["items"])
    act = client.get("/customers", params={"active": "true", "min_products": 3, "limit": 500}).json()
    assert all(i["active"] == 1 and i["num_products"] >= 3 for i in act["items"])
    name = r["items"][0]["surname"]
    hit = client.get("/customers", params={"search": name[:4].lower()}).json()
    assert hit["total"] >= 1 and all(name[:4].lower() in i["surname"].lower() for i in hit["items"])
    by_id = client.get("/customers", params={"search": r["items"][3]["customer_id"]}).json()
    assert by_id["total"] == 1
    page2 = client.get("/customers", params={"limit": 10, "offset": 10}).json()
    assert page2["items"][0]["customer_id"] == r["items"][10]["customer_id"]


def test_detail_has_drivers_with_values_and_offers(client):
    cid = client.get("/customers", params={"limit": 1}).json()["items"][0]["customer_id"]
    d = client.get(f"/customers/{cid}").json()
    assert d["surname"] and d["exited"] in (0, 1) and len(d["top_drivers"]) == 5
    assert all("value" in x and "contribution" in x for x in d["top_drivers"])
    assert d["offers"], "at least one eligible offer"
    for o in d["offers"]:
        assert o["new_p_churn"] <= d["p_churn_calibrated"] + 1e-9
        assert o["value_kept"] >= 0
    assert sum(o["best"] for o in d["offers"]) <= 1


def test_points_cover_every_customer(client):
    r = client.get("/customers/points").json()
    n = client.get("/customers", params={"limit": 1}).json()["total"]
    assert len(r["customer_id"]) == len(r["p"]) == len(r["value"]) == len(r["band"]) == n


def test_home_rows(client):
    rows = client.get("/home/rows").json()["rows"]
    assert [r["key"] for r in rows] == ["top", "country", "products", "staying", "others"]
    assert len(rows[0]["items"]) == 10 and all(len(r["items"]) <= 30 for r in rows)
    assert all(i["exited"] == 0 for i in rows[3]["items"])
    assert all(i["num_products"] >= 3 for i in rows[2]["items"])
    country = rows[1]["title"].split(",")[0]
    assert all(i["geography"] == country for i in rows[1]["items"])
    assert rows[1]["count"] >= len(rows[1]["items"])


def test_stats(client):
    p = client.get("/stats/products").json()["by_products"]
    assert sum(r["customers"] for r in p) == 200 and all(0 <= r["rate"] <= 1 for r in p)
    rates = client.get("/stats/rates").json()
    assert {"geography", "active", "age_band", "tenure_band", "credit_band"} <= set(rates)


def test_allocate_totals_by_offer_and_segment(client):
    a = client.post("/allocate", json={"budget": 2000, "strategy": "segment_aware"}).json()
    assert a["n_targeted"] > 0
    assert sum(o["customers"] for o in a["by_offer"]) == a["n_targeted"]
    assert sum(o["customers"] for o in a["by_segment"]) == a["n_targeted"]
    assert abs(sum(o["spend"] for o in a["by_offer"]) - a["spent"]) < 1
    assert abs(sum(o["expected_revenue_saved"] for o in a["by_offer"]) - a["expected_revenue_saved"]) < 1


def test_allocate_export_has_every_targeted_row(client):
    a = client.post("/allocate", json={"budget": 2000, "strategy": "uniform"}).json()
    r = client.get("/allocate/export", params={"budget": 2000, "strategy": "uniform"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert len(r.text.strip().splitlines()) - 1 == a["n_targeted"]


def test_allocate_curve_is_monotone_and_cached(client, monkeypatch):
    from api.routers import allocate as al
    monkeypatch.setattr(al, "CURVE_BUDGETS", [1000, 2000, 4000])
    al._curves.clear()
    c = client.post("/allocate/curve", json={"strategy": "segment_aware"}).json()["points"]
    assert [p["budget"] for p in c] == [1000, 2000, 4000]
    saved = [p["expected_revenue_saved"] for p in c]
    assert saved == sorted(saved) and saved[-1] > 0
    assert all(p["spent"] <= p["budget"] + 1e-6 for p in c)
    again = client.post("/allocate/curve", json={"strategy": "segment_aware"}).json()["points"]
    assert again == c


def test_scores_are_out_of_fold():
    """Real artifacts only: customers the model trained on must not look better than held-out ones."""
    import json
    import pandas as pd
    from sklearn.metrics import average_precision_score as ap
    art = ROOT / "artifacts"
    if not (art / "leakage_check.json").exists():
        pytest.skip("out-of-fold artifacts not built (run `make oof`)")
    s = pd.read_parquet(art / "scores.parquet")
    train, test = s[s.split == "train"], s[s.split == "test"]
    gap = ap(train.churned, train.p_churn_calibrated) - ap(test.churned, test.p_churn_calibrated)
    assert gap < 0.08, f"train rows look in-sample (PR-AUC gap {gap:.3f})"
    leak = json.loads((art / "leakage_check.json").read_text())
    assert leak["before"]["train_in_sample"]["pr_auc"] - leak["before"]["test_holdout"]["pr_auc"] > 0.1
    if "all_oof_crossfit" in leak["after"]:
        assert 0 < leak["after"]["all_oof_crossfit"]["ece"] < 0.05


def test_shortlist_and_sent_offers_are_recorded(client):
    cid = client.get("/customers", params={"limit": 1}).json()["items"][0]["customer_id"]
    client.delete(f"/shortlist/{cid}")
    assert cid not in client.get("/shortlist").json()["customer_ids"]
    assert cid in client.put(f"/shortlist/{cid}").json()["customer_ids"]
    assert client.put(f"/shortlist/{cid}").json()["customer_ids"].count(cid) == 1
    assert cid not in client.delete(f"/shortlist/{cid}").json()["customer_ids"]
    assert client.put("/shortlist/NOPE-404").status_code == 404
    sent = client.post("/offers/send", json={"customer_id": cid, "offer": "fee_waiver"}).json()
    assert sent["customer_id"] == cid and sent["sent_at"]
    assert client.get("/offers/sent").json()["items"][0]["offer"] == "fee_waiver"
    assert client.post("/offers/send", json={"customer_id": "NOPE-404"}).status_code == 404
