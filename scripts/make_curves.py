"""Pre-compute the budget curves (value kept at 100K to 5M) so the dashboard does not wait for the solver.

Usage: PYTHONPATH=src python scripts/make_curves.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from api.routers import allocate  # noqa: E402


def main() -> None:
    for strategy in ("segment_aware", "uniform", "risk_proportional"):
        pts = allocate.allocate_curve(allocate.CurveRequest(strategy=strategy))["points"]
        print(f"{strategy}: {len(pts)} budgets, value kept at 1M = "
              f"{next(p['expected_revenue_saved'] for p in pts if p['budget'] == 1_000_000):,.0f}")


if __name__ == "__main__":
    main()
