# Redesign inventory (pre-redesign behaviour that must survive)

All calls go through relative URLs (Vite proxy) via `src/api.ts` (React Query).

## App
- Tab state (Overview, Client Lookup, Budget Planner, Model & Data), default Overview.

## Overview
- API: `GET /portfolio/summary` (`n_customers`, `total_revenue_at_risk`, `band_counts`, `by_segment[segment_name, customers, revenue_at_risk]`), `GET /forecast?scenario=<s>` (`points[month, actual, forecast, lower, upper]`).
- Interactive: scenario toggle (`no_intervention`, `with_allocation`) re-fetches forecast.
- Display: 4 KPIs (Customers, Revenue at risk, Red band, Segments), band donut, segment bars, forecast line chart (Actual/Forecast/Lower/Upper), loading and API-unavailable messages.

## Client Lookup
- API: `GET /customers?limit=500[&risk_band=<b>]`, `GET /customers/{id}` (enabled when a row is selected), link to `GET /customers/{id}/report.pdf` (new tab).
- Interactive: search box (client-side filter on customer_id), band filter (all/red/amber/green; server-side), row click selects customer.
- Table fields: customer_id, p_churn_calibrated, risk_band, revenue_at_risk, segment_name. Footer: shown count of total.
- Detail fields: customer_id, risk_band, p_churn_calibrated, p_churn_raw, revenue_at_risk, segment (name, value_tier), top_drivers (label, contribution), allocation (offer, spend, expected_revenue_saved, reason), PDF download link.
- States: empty prompt, loading.

## Budget Planner
- API: `POST /allocate {budget, strategy}` -> `budget`, `spent`, `expected_revenue_saved`, `allocations[customer_id, value_tier, offer, spend, expected_revenue_saved, reason]`.
- Interactive: budget number input (min 1000, step 10000, default 1,000,000), strategy (segment_aware, uniform, risk_proportional), Run allocation (disabled + "Optimising…" while pending), error message on failure.

## Model & Data
- API: `GET /model/metrics` (`models[name, valid_pr_auc, valid_brier, valid_ece]`, `best_model`, `calibration`, `test{pr_auc_calibrated, brier_calibrated, pr_auc_raw, brier_raw, ece_raw, ece_calibrated}`, `threshold{threshold, n_flagged, cost}`, `calibration_curve[bin_mean_pred, bin_frac_pos, n]`).
- Display: 4 KPIs, model comparison table (best highlighted), calibration chart with diagonal, operating point text.
