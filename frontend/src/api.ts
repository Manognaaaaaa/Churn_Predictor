import { useQuery, useMutation } from "@tanstack/react-query";

async function get<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}

export interface CustomerRow {
  customer_id: string;
  p_churn_calibrated: number;
  risk_band: "green" | "amber" | "red";
  revenue_at_risk: number;
  segment_name: string | null;
  value_tier: string | null;
}
export interface CustomerDetail extends CustomerRow {
  snapshot_date: string;
  p_churn_raw: number;
  top_drivers: { feature: string; label: string; contribution: number }[];
  segment: { segment_id: number; segment_name: string; value_tier: string } | null;
  allocation: { offer: string; spend: number; expected_revenue_saved: number; reason: string } | null;
}
export interface PortfolioSummary {
  n_customers: number;
  total_revenue_at_risk: number;
  band_counts: Record<string, number>;
  by_segment: { segment_name: string; customers: number; revenue_at_risk: number }[];
}
export interface ForecastPoint {
  month: string;
  actual: number | null;
  forecast: number | null;
  lower: number | null;
  upper: number | null;
}
export interface Allocation {
  customer_id: string;
  segment_id: number;
  value_tier: string;
  offer: string;
  spend: number;
  expected_revenue_saved: number;
  reason: string;
}

export const useHealth = () => useQuery({ queryKey: ["health"], queryFn: () => get<{status: string}>(`/health`) });
export const usePortfolio = () => useQuery({ queryKey: ["portfolio"], queryFn: () => get<PortfolioSummary>(`/portfolio/summary`) });
export const useForecast = (scenario: string) =>
  useQuery({ queryKey: ["forecast", scenario], queryFn: () => get<{scenario: string; points: ForecastPoint[]}>(`/forecast?scenario=${scenario}`) });
export const useMetrics = () => useQuery({ queryKey: ["metrics"], queryFn: () => get<any>(`/model/metrics`) });
export const useCustomers = (band: string, limit: number) =>
  useQuery({
    queryKey: ["customers", band, limit],
    queryFn: () => get<{ total: number; items: CustomerRow[] }>(`/customers?limit=${limit}${band ? `&risk_band=${band}` : ""}`),
  });
export const useCustomer = (id: string | null) =>
  useQuery({ queryKey: ["customer", id], queryFn: () => get<CustomerDetail>(`/customers/${id}`), enabled: !!id });

export async function allocate(budget: number, strategy: string): Promise<any> {
  const r = await fetch(`/allocate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ budget, strategy }),
  });
  if (!r.ok) throw new Error(`allocate: ${r.status}`);
  return r.json();
}
export const useAllocate = () =>
  useMutation({ mutationFn: ({ budget, strategy }: { budget: number; strategy: string }) => allocate(budget, strategy) });

export function fmtMoney(x: number | null | undefined, digits = 0): string {
  if (x == null || isNaN(x)) return "–";
  return x.toLocaleString("en-US", { maximumFractionDigits: digits });
}
