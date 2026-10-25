import { useQuery } from "@tanstack/react-query";

async function get<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}
async function post<T>(url: string, body: unknown, signal?: AbortSignal): Promise<T> {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal });
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}

export type Band = "red" | "amber" | "green";

export interface Customer {
  customer_id: string;
  surname: string | null;
  gender: string | null;
  age: number | null;
  geography: string | null;
  tenure: number | null;
  balance: number | null;
  num_products: number | null;
  credit_score: number | null;
  active: number | null;
  estimated_salary: number | null;
  exited: number | null;
  p_churn_calibrated: number;
  risk_band: Band;
  revenue_at_risk: number;
  segment_name: string | null;
  value_tier: string | null;
}
export interface Driver { feature: string; label: string; value: number | null; contribution: number }
export interface OfferOption { offer: string; cost: number; new_p_churn: number; value_kept: number; net_value_kept: number; best: boolean }
export interface CustomerDetail extends Customer {
  snapshot_date: string;
  p_churn_raw: number;
  top_drivers: Driver[];
  offers: OfferOption[];
  allocation: { offer: string; spend: number; expected_revenue_saved: number; reason: string } | null;
}
export interface HomeRow { key: string; title: string; count: number; rate: number | null; items: Customer[] }
export interface RateRow { key: string; customers: number; left: number; rate: number }
export interface Rates { geography: RateRow[]; active: RateRow[]; age_band: RateRow[]; tenure_band: RateRow[]; credit_band: RateRow[] }
export interface ProductRate { num_products: number; customers: number; left: number; rate: number }
export interface AllocationResult {
  budget: number;
  spent: number;
  expected_revenue_saved: number;
  strategy: string;
  n_targeted: number;
  by_offer: { offer: string; customers: number; spend: number; expected_revenue_saved: number }[];
  by_segment: { segment_name: string; customers: number; spend: number; expected_revenue_saved: number }[];
}
export interface CurvePoint { budget: number; spent: number; expected_revenue_saved: number; n_targeted: number }
export interface PortfolioSummary {
  n_customers: number;
  total_revenue_at_risk: number;
  band_counts: Record<string, number>;
  by_segment: { segment_name: string; customers: number; revenue_at_risk: number }[];
}
interface Qual { pr_auc: number; brier: number; ece: number }
interface Dist {
  mean: number;
  quantiles: Record<string, number>;
  n_eq_1: number;
  band_counts: Record<string, number>;
  [k: string]: unknown;
}
export interface LeakageCheck {
  method: string;
  before: { distribution: Dist; train_in_sample: Qual; test_holdout: Qual };
  after: { distribution: Dist; all_oof: Qual; all_oof_crossfit?: Qual; train_rows_oof: Qual; test_rows_oof: Qual };
}
export interface Metrics {
  models: { name: string; valid_pr_auc?: number; valid_brier?: number; valid_ece?: number }[];
  best_model: string;
  calibration: string;
  test: Record<string, number>;
  threshold: { threshold?: number; n_flagged?: number; cost?: number };
  calibration_curve: { bin_mean_pred: number; bin_frac_pos: number; n: number }[];
  leakage_check?: LeakageCheck | null;
  trained_at?: string | null;
}

export interface CustomerQuery {
  search?: string; band?: string; country?: string; min_products?: number; active?: boolean; limit?: number; offset?: number;
}
function qs(q: Record<string, unknown>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(q)) if (v !== undefined && v !== "" && v !== null) p.set(k, String(v));
  return p.toString();
}
export const fetchCustomers = (q: CustomerQuery, signal?: AbortSignal) =>
  fetch(`/customers?${qs({ ...q })}`, { signal }).then((r) => {
    if (!r.ok) throw new Error(`customers: ${r.status}`);
    return r.json() as Promise<{ total: number; items: Customer[] }>;
  });

export const useHomeRows = () => useQuery({ queryKey: ["home"], queryFn: () => get<{ rows: HomeRow[] }>("/home/rows") });
export const usePortfolio = () => useQuery({ queryKey: ["portfolio"], queryFn: () => get<PortfolioSummary>("/portfolio/summary") });
export const useCustomer = (id: string | null) =>
  useQuery({ queryKey: ["customer", id], queryFn: () => get<CustomerDetail>(`/customers/${id}`), enabled: !!id });
export const useProductRates = () => useQuery({ queryKey: ["products"], queryFn: () => get<{ by_products: ProductRate[] }>("/stats/products"), staleTime: Infinity });
export const useRates = () => useQuery({ queryKey: ["rates"], queryFn: () => get<Rates>("/stats/rates"), staleTime: Infinity });
export const useMetrics = () => useQuery({ queryKey: ["metrics"], queryFn: () => get<Metrics>("/model/metrics"), staleTime: Infinity });
export const useCurve = (strategy: string) =>
  useQuery({ queryKey: ["curve", strategy], queryFn: () => post<{ points: CurvePoint[] }>("/allocate/curve", { strategy }), staleTime: Infinity });

export const allocate = (budget: number, strategy: string, signal?: AbortSignal) =>
  post<AllocationResult>("/allocate", { budget, strategy }, signal);
