# Plain-language inventory

Analyst view keeps the current text. Manager view uses the new text. Headline sentences appear in both views.

## Answers from the code

**What is "revenue" computed from?**
`revenue_at_risk = p_churn_calibrated x customer_value`. `customer_value` is the `EstimatedSalary` column of Churn_Modelling (`configs/config.yaml`: `value_col: EstimatedSalary`, "customer value proxy for revenue-at-risk"). It is not bank revenue. No period is defined (the data is a static snapshot with no dates). Currency is `EUR` (`datasets.churn_modelling.currency`). The UI uses the euro sign for every customer-level figure. The forecast chart is a different series: weekly sales of a UK retailer (Online Retail II), currency `GBP` (`forecast.currency`), so it uses the pound sign.

**How are segment names built?**
`src/churn/risk/segments.py`: a Gaussian mixture splits customers into clusters. Each cluster is named `<most distinctive feature> (<sign><gap> sd)`, where the gap is how many standard deviations the cluster mean is from the portfolio mean (`+1.7 sd` = 1.7 standard deviations above average). When two clusters get the same name, later ones get ` #<cluster id>` (`#7` is the cluster index, not a rank). Real names today: `Geography_France (+1.0 sd)`, `Geography_Germany (+1.7 sd)`, `Geography_Germany (+1.7 sd) #7`, `Geography_Spain (+1.7 sd)`, `... #3`, `... #5`, `zero_balance (+1.3 sd)`, `zero_balance (+1.3 sd) #6`.

**Offer codes (config `allocation.offers`)**
| Code | Cost | Shown as |
|---|---|---|
| `loyalty_email` | 5 flat, any customer | Loyalty email |
| `fee_waiver` | 25 flat, any customer | Waive fees |
| `service_call` | 100 flat, less engaged customers | Personal service call |
| `retention_bonus` | 250 flat, mid and high value, engaged customers | Retention bonus |
| `value_discount` | 0.5% of customer value, engaged customers | Discount on plan |

**Forecast chart**
x axis: weeks (week ending Sunday, `freq: W-SUN`; the parquet column is still called `month`). The solid history is actual weekly retailer revenue. The spikes are real seasonality: the Christmas peak (week of 12 Dec 2010 is 583K) and a few near-empty weeks (one week is 55K). The forecast is 12 weeks of ARIMA. The two scenarios are `forecast x (1 - L)` and `forecast x (1 - L')`, where `L` is the expected churn loss rate (20.6%) and `L'` is that rate after the allocation (config comments, `forecast_meta.json`). So the plotted line is expected revenue, not revenue at risk. The Manager title says so.

**Risk bands (`risk_bands`, calibrated probability)**
Low (green): up to and including 20%. Medium (amber): above 20% and up to 50%. High (red): above 50%.

## Backend limits that shape the UI
- `GET /customers` returns at most 500 rows and has no offer field, so the Customers table cannot show a suggested offer and the group filter works on the 500 loaded rows.
- `POST /allocate` returns at most 500 allocation rows (the largest by revenue kept) plus `n_targeted`, so the CSV export holds those rows, not the full list.
- No per-customer test outcomes and no segment profile are exposed, so the "top 10% flagged" statistic and group descriptions are not shown.
- The PDF report is produced by the backend and still uses technical wording.

## Overview
| Element | Analyst (current) | Manager (new) |
|---|---|---|
| Tab | Overview | Summary |
| Headline | new | "**N customers** are at high risk of leaving. Together, customers put **€X** of revenue at risk. **Group** carries the largest share (**Y%**)." |
| KPI 1 | Customers | Customers |
| KPI 2 | Revenue at risk | Revenue at risk (+ info) |
| KPI 3 | Red band | High-risk customers (delta "12% of customers") |
| KPI 4 | Segments | Revenue saved with current budget (after a run), else Customer groups |
| Donut title | Risk bands | How many customers are at risk |
| Donut legend | green / amber / red | High risk 1,232 (12%), Medium risk, Low risk; centre "high risk" |
| Bar title | Revenue at risk by segment | Where the revenue at risk is |
| Bar labels | raw segment name | `segmentLabel`, sorted, compact value at bar end, % of total in tooltip |
| Forecast title | Revenue at risk forecast | Expected weekly revenue |
| Forecast caption | none | x axis, dashed line, rolling average note |
| Toggle | No intervention / With allocation | If we do nothing / If we spend the budget |
| Series | Actual, Forecast, Lower, Upper | Weekly revenue (4-week average, raw faint), Forecast, Likely range |
| Under chart | none | Difference between the scenarios |
| Loading / error | Loading… / API unavailable. Is `make api` running? | Loading… / The data is not available. Check that the API is running. |

## Customers
| Element | Analyst | Manager |
|---|---|---|
| Tab | Client Lookup | Customers |
| Headline | new | "Showing N high-risk customers, sorted by revenue at risk. Click a customer to see why they might leave and what to offer." |
| Search | Search customer id | Search customer ID |
| Band filter | all / red / amber / green | All / High risk / Medium risk / Low risk |
| Group filter | none | dropdown of groups |
| Columns | Customer, P(churn), Band, Revenue at risk, Segment | Customer, Chance of leaving, Risk, Revenue at risk (€), Group |
| Footer | "N of M shown (top 500 by revenue at risk)" | "N of M customers shown (the 500 with the most revenue at risk)" |
| Empty state | Select a customer to see their risk profile. | Select a customer to see why they might leave and what to offer them. |
| Detail title | Risk profile / Customer | Customer <id> + BandPill + summary sentence |
| Probability | calibrated %, "churn · raw %" | sentence with `chanceText` |
| Drivers | Top churn drivers (SHAP) with numbers | Why the model thinks this: top 3, "Show all reasons", legend raises/lowers risk, no numbers |
| Segment line | Segment: name · tier value | Group + value level in the summary |
| Recommendation | Recommended / mono offer code / Spend → save | Recommended action / offer label / "Spend 500 to keep an expected 2,936 of revenue." |
| Button | Download PDF report | Download customer report |

## Retention budget
| Element | Analyst | Manager |
|---|---|---|
| Tab | Budget Planner | Retention budget |
| Headline | new (after run) | "Spending X is expected to keep Y of revenue, a return of Zx. That is P% more than spreading the budget evenly." |
| Caption | step-6 KKT water-filling text | Strategy tip (plain) |
| Budget input | Budget (number) | Budget to spend on retention offers (€), thousands separators, chips 250K / 500K / 1M / 2M |
| Strategy | KKT segment-aware / Uniform split / Risk-proportional | Best return (recommended) / Same amount for everyone / Most at-risk first |
| Run button | Run allocation / Optimising… | Show the plan / Working… |
| KPIs | Budget, Spent, Expected revenue saved | Budget, Spent, Expected revenue saved, Return on budget |
| Chart | none | Revenue saved by strategy |
| Columns | Customer, Tier, Offer, Spend, Revenue saved | Customer, Group, Offer, Cost (€), Revenue kept (€) |
| Footer | none | Showing 50 of N customers who get an offer; Download list (CSV) |

## Can we trust this?
| Element | Analyst | Manager |
|---|---|---|
| Tab | Model & Data | Can we trust this? |
| Headline | new | reliability sentence (second sentence only when test calibration error is under 5%) |
| Content | 4 KPIs, comparison table, calibration chart, operating point | 4 panels (finding leavers, percentages match reality, which model, when it flags a customer) |
| Calibration axes | none (default) / "Observed churn rate" | Predicted chance of leaving / Share who actually left; legend Perfect match / Our model |
| Table headers | PR-AUC, Brier, ECE | Precision at top, Error of the percentages, Calibration gap (info tips carry the technical names) |
| Model names | Logistic (MLE), Logistic (MAP), ... LSTM | Logistic regression, Regularised logistic regression, ..., Sequence neural network |
| Operating point | Cost-optimal threshold ..., flagged, minimised cost, raw vs calibrated | "flags a customer when their chance of leaving is above 6%..." |
