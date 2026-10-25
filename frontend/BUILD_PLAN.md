# Build plan: cinematic blue dashboard

Status: plan only. No app code has been changed. Waiting for a go-ahead.
This replaces the earlier navy-dashboard plan.

## 0. What I read
`frontend/` (package.json, tailwind config, App, pages, components, lib, API client), the backend routes and pipeline (`run_train.py`, `run_risk.py`, `segments.py`, allocation `groups.py`/`offers.py`/`solver.py`, `explain.py`, `config.yaml`), and both reference files in full or in the relevant parts: `cinematic_app.html` (all of it) and `motion_library.html` (search panel, drawn chart, shimmer).

The reference folder is not in the repo. It lives at `C:\Users\manog\OneDrive\Desktop\UNI\sem 7\fds\design_reference`. I will copy it to `design_reference/` in the repo root. `support.js` is not in it and not needed.

## 1. Two data problems (both confirmed)

### 1.1 Value is estimated salary
`revenue_at_risk = p x EstimatedSalary` (config: `value_col: EstimatedSalary`, "customer value proxy"). The UI will say "yearly value" everywhere, with the Model page note: "Yearly value is the customer's estimated salary from the dataset." No currency symbol is shown in the reference (it uses bare numbers), so I will show none.

### 1.2 Leakage in the scores shown
`run_train.py` fits on the train split, then scores all 10,000 rows with that model, so 7,000 customers are scored in-sample. All six customers you named are in the train split with p = 1.0 and `Exited = 1`.

| Split | Rows | PR-AUC | ROC-AUC | p >= 0.99 | p <= 0.01 |
|---|---|---|---|---|---|
| train (in-sample) | 7,000 | 0.886 | 0.972 | 253 (3.6%) | 1,217 (17.4%) |
| valid | 1,500 | 0.711 | 0.888 | 29 (1.9%) | 208 (13.9%) |
| test (held out) | 1,500 | 0.676 | 0.858 | 34 (2.3%) | 206 (13.7%) |

Fix, as you asked ("out-of-fold with the same model and calibration"):
- 5-fold stratified OOF predictions for all 10,000 rows using the chosen model with the same hyper-parameters and imbalance strategy.
- Same calibration method (isotonic, as chosen), fit on the OOF raw scores. This is a 1-D monotone map on 10,000 points, so the optimism of fitting and applying it on the same scores is negligible. I will say so in the summary.
- `scores.parquet` is rewritten from OOF calibrated probabilities. The existing held-out test metrics stay in `metrics.json` (they were already honest). I add OOF metrics and a `leakage_check` block (in-sample vs OOF vs test) which feeds the Model page panel.
- SHAP drivers still come from the final model; they explain features, not labels.
- Then I re-run `make risk allocate claims` and the tests. Every headline number changes (208.1M at risk, 1,232 high risk, 1.93M kept at 1M, forecast scenarios, claims reports). The top-10 customers will not be the same people as in the reference mock.

## 2. Gaps between the reference and the real data (things you should know)

1. **Offers.** The reference shows 3 offers with made-up costs (300 / 500 / 900). The real catalog has 5: `loyalty_email` (5), `fee_waiver` (25), `service_call` (100), `retention_bonus` (250), `value_discount` (0.5% of value, only eligible while cost <= the 500 cap). A customer only sees offers they are eligible for. The "new chance of leaving" comes from the allocation response curve `p x (1 - a_g x (1 - exp(-cost / tau)))`, an assumption (config says there is no uplift data), so the modal labels it "estimated". Real offer costs are small against yearly value, so effects look small next to the mock.
2. **Money-flow animation.** The reference sends dots to 3 offer types. The real by-offer totals have 5 types, so the flight diagram will have 5 targets (taller canvas, 340px instead of 230px). Names (proposed): `value_discount` "Better savings rate", `fee_waiver` "Waive account fees", `service_call` "Call from relationship manager", `retention_bonus` "Loyalty bonus", `loyalty_email` "Personal email from the bank".
3. **"Customers reached"** in the reference is `budget / 470`. I use the real `n_targeted`.
4. **Home rows hold thousands of customers** (Germany alone is about 2,500). `/home/rows` returns the true count and the first 30 by value at risk for each row. The arrows page through those 30 (6 pages of 5).
5. **Row titles come from data.** "Germany, the highest leaving rate" is only printed if Germany really has the highest rate; the backend picks the country and quotes its rate.
6. **Header search** is a server search (`/customers?search=`), since 10,000 names cannot sit in the browser list.
7. **Touch targets.** The reference's round card buttons are 28px and chips 38px. You asked for 36px minimum (44px on touch), so I enlarge them. Small visible difference from the reference.
8. **Model updated.** The reference says "Model updated today". I add `trained_at` (model file time) to `/model/metrics` and show the real date.
9. **Shortlist ("+") and "Send offer".** There is no backend table for either. Plan: shortlist and sent offers live in a local store (React state mirrored to `localStorage`, in try/catch), with a toast. No server write. Say if you want a real endpoint instead.
10. **Gender is binary in the data**, so "Mr/Ms" follows it. I use "Customer" + id if Surname/Gender is missing.

## 3. Sections, data, endpoints

OK = supplied today. MISSING = backend change in section 4.

| Page / section | Data needed | Today | Status |
|---|---|---|---|
| Intro | none | | OK |
| Header: model date | model timestamp | none | MISSING: `trained_at` in `/model/metrics` |
| Header: search panel | name or id search, band, value | `/customers` has no names or search | MISSING: `GET /customers?search=` |
| Home billboard (top 4) | top 4 by value at risk with raw fields, p, story inputs | no names/raw fields | MISSING: from `/home/rows` row "top" |
| Home rows (5) | per row: title, true count, rate, first 30 customers (name, country, age, products, active, value, p, band) | none | MISSING: `GET /home/rows` |
| Customers grid | filtered, paginated customer list, total count | `/customers` capped, no filters | MISSING: extended `GET /customers` (search, band, country, min_products, active, sort, limit, offset) |
| Profile modal: header and facts | all raw fields incl. `Exited` | partial | MISSING: extended `GET /customers/{id}` |
| Profile: gauge and offers | p, eligible offers with cost, new p, value kept | allocation info only | MISSING: `offers[]` in `GET /customers/{id}` |
| Profile: drivers | top 5 SHAP: feature, value, contribution | feature and contribution only | MISSING: add `value` |
| Profile: sentences with real rates | churn rate per product count (and other features) | none | MISSING: `GET /stats/products` (+ `GET /stats/rates` for geography, active, age band) |
| Profile: PDF | report | `/customers/{id}/report.pdf` | OK (the PDF text keeps its old wording) |
| Budget: slider, tiles | spent, value kept, n_targeted | `POST /allocate` | OK |
| Budget: strategy cards | value kept at the current budget per strategy | 3 parallel calls today | MISSING: `POST /allocate/curve` |
| Budget: money to offers | totals by offer (customers, spend, value kept) and by segment | none | MISSING: `by_offer`, `by_segment` on `POST /allocate` |
| Budget: CSV of the full list | every targeted customer | 500 row cap | MISSING: `GET /allocate/export` (or `rows=all`) |
| Model: metrics, table, calibration curve | `/model/metrics` | | OK |
| Model: leakage panel | in-sample vs OOF vs test | none | MISSING: `leakage_check` in `/model/metrics` |

## 4. Backend changes (each with a pytest)
Endpoint names: the prompt writes `/allocation`, the existing route is `/allocate`. I keep `/allocate` and add `/allocate/curve` and `/allocate/export`. All changes are additive, so nothing existing breaks. I add the new paths (`/home`, `/stats`) to the Vite proxy.

| Change | Files |
|---|---|
| OOF scoring + isotonic on OOF; write `artifacts/customers.parquet` (raw columns, so the API never reads `data/raw`, which is absent in CI); `leakage_check`; `trained_at` | `src/churn/pipeline/run_train.py`, new `src/churn/models/oof.py` |
| SHAP drivers with raw feature value | `src/churn/models/explain.py`, `run_train.py` |
| `GET /customers` extended | `src/api/routers/customers.py` |
| `GET /customers/{id}` extended (raw fields, drivers with value, offers) | same |
| `GET /home/rows` | new `src/api/routers/home.py` |
| `GET /stats/products`, `GET /stats/rates` | new `src/api/routers/stats.py` |
| `POST /allocate` adds `by_offer`, `by_segment`; `POST /allocate/curve` (cached in memory and in `artifacts/allocation_curve_<strategy>.json`, lazy per strategy; one solve is about 0.34 s, so about 17 s per strategy for 50 budgets; also `make curve`); `GET /allocate/export` | `src/api/routers/allocate.py` |
| Mock artifacts get the new columns | `scripts/make_mocks.py` |
| Tests | `tests/test_step10_api.py` (mock-backed, like the step 7 tests) + a leakage test (OOF scores of train rows must not separate labels much better than test rows) |

## 5. Frontend

### 5.1 Foundations
- `styles/tokens.css`: your tokens, plus names for the reference colours that are not in your list (`--blue-ring-end`, poster gradients for Germany/France/Spain, `--glow-*`) so no raw hex appears in components. `tailwind.config.js` maps them. Geist via Google Fonts in `index.html`, weight 300 for big numbers, 600 for names, `tnum` on the root.
- `lib/theme.ts` (`cssVar`), `lib/format.ts` (`full`, `short`, `pct`), `lib/plain.ts` (`customerName`, `offerLabel`, `segmentLabel`, `featureLabel`).
- `hooks/useReducedMotion.ts` (gates the intro, tweens, billboard rotation), `hooks/useSessionFlag.ts`, `hooks/useTween.ts` (used for the odometer-free number tweens).
- Dependencies added: `framer-motion`, plus `@playwright/test` (dev) and `lighthouse` (dev, via npx) for the checks. Removed if unused: `recharts` (the Model chart is a drawn SVG, as in the motion library).

### 5.2 Components to create
`Intro`, `Header` (with sliding `layoutId` underline), `SearchPanel`, `Billboard`, `RiskRing` (mini and large), `PosterBackground`, `CustomerCard` (row card), `GridCard`, `CardRow` (carousel with arrows, pips, rank numerals), `Customers` page with filters and infinite pagination, `ProfileModal` (dialog, focus trap, return focus), `Gauge` (spring needle), `OfferList`, `FactTile`, `DriverBar`, `Odometer`, `FlightDiagram` (offset-path dots), `StrategyCard` (conic border), `BudgetSlider`, `Toast`, `Skeleton`, `DrawnChart` (self-drawing line, crosshair), `ModelPage` panels, `LeakagePanel`, plus stores: `ModalContext`, `ShortlistContext`. Old pages and the old `ui/` components are deleted when replaced.

### 5.3 Motion
Keyframes copied from the reference where simple (intro, ken burns, ring draw, story progress, sheen, orbit, drift, money dots, conic spin, toast). framer-motion for: `AnimatePresence` screen transitions, modal enter/exit, grid stagger (55 ms), nav underline `layoutId`. Reduced motion: no intro, final states at once, billboard rotation stopped. Animate only `transform` and `opacity` plus the SVG properties the reference animates (`stroke-dasharray`, `stroke-dashoffset`, `offset-distance`, `width` on the story bar). `will-change` only while a card is hovered.

### 5.4 Quality gates
Responsive at 390px (billboard stacks, 2 cards per row, 1-column grid, full-screen modal, no sideways scroll except card rows), skeleton shimmer on load, plain empty and error sentences per list, contrast 4.5:1 (`--ink-faint` only for 12px+ secondary text; computed about 5:1 on `--bg`), Lighthouse performance >= 85 on Home, Model page lazy-loaded, rows render the visible page plus the next.

## 6. Build order
1. Copy `design_reference/`; branch `feature/cinematic-dashboard`.
2. Backend: OOF fix, endpoints, tests; re-run pipeline; record before/after.
3. Tokens, fonts, shared libs and hooks.
4. Header, intro, Home (billboard, rows), modal, Customers, Budget, Model.
5. Playwright screenshots at 1440 and 390 against the reference, text greps, keyboard and reduced-motion checks, Lighthouse.

## 7. Things I will not be able to match exactly
- Reference numbers (names, top-10 order, 1,925,637 kept) come from sample or in-sample values and will differ after the OOF fix.
- 5 offer types instead of 3 in the flight diagram.
- Slightly larger touch targets than the reference.
- No server persistence for shortlist or sent offers (unless you ask).

## 8. Assumptions I will make unless you say otherwise
- Branch from `feature/manager-view` (it holds the plain-language helpers and the Trust-page copy that the Model page reuses). The Manager/Analyst switch goes away; the Model page keeps all numbers.
- Install Playwright and Lighthouse as dev tools (browser download about 150 MB).
- Offer names in section 2, item 2.
- `/allocate` naming and local-only shortlist and "Send offer".
