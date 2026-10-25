import { fmtMoney } from "./format";
import type { Band } from "../components/ui/BandPill";

/** Currencies from configs/config.yaml: customer values are EUR, the revenue forecast series is GBP. */
export const CUSTOMER_CURRENCY = "€";
export const FORECAST_CURRENCY = "£";

/** Probability cut-offs of configs/config.yaml `risk_bands` (calibrated probability). */
export const BAND_LIMITS = { greenMax: 0.2, amberMax: 0.5 };

const cleanBase = (raw: string) =>
  raw.replace(/\s*\([+-]?[\d.]+ sd\)/, "").replace(/\s*#\d+\s*$/, "").trim();

function baseLabel(raw: string): string {
  const base = cleanBase(raw);
  const negative = /\(-[\d.]+ sd\)/.test(raw);
  if (base.startsWith("Geography_")) return `Customers in ${base.slice("Geography_".length).replace(/_/g, " ")}`;
  if (base === "zero_balance") return negative ? "Customers with an account balance" : "Customers with no account balance";
  return base.replace(/_/g, " ");
}

/** Readable name for one raw segment name, without group letters. */
export function segmentLabel(raw: string | null | undefined): string {
  return raw ? baseLabel(raw) : "–";
}

/**
 * Builds a labeller from the full list of segment names. Names that share a readable label get
 * group letters in order of first appearance (A, B, C...).
 */
export function buildSegmentLabeler(names: string[]): (raw: string | null | undefined) => string {
  const byLabel = new Map<string, string[]>();
  for (const n of names) {
    const l = baseLabel(n);
    byLabel.set(l, [...(byLabel.get(l) ?? []), n]);
  }
  return (raw) => {
    if (!raw) return "–";
    const l = baseLabel(raw);
    const group = byLabel.get(l) ?? [];
    return group.length > 1 && group.includes(raw) ? `${l} (group ${String.fromCharCode(65 + group.indexOf(raw))})` : l;
  };
}

const OFFERS: Record<string, string> = {
  loyalty_email: "Loyalty email",
  fee_waiver: "Waive fees",
  service_call: "Personal service call",
  retention_bonus: "Retention bonus",
  value_discount: "Discount on plan",
};
export function offerLabel(code: string | null | undefined): string {
  if (!code) return "–";
  if (OFFERS[code]) return OFFERS[code];
  const s = code.replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function riskWord(band: Band): string {
  return band === "red" ? "High risk" : band === "amber" ? "Medium risk" : "Low risk";
}

/** Churn probability as a manager reads it. */
export function chanceText(p: number | null | undefined): string {
  if (p == null || isNaN(p)) return "–";
  if (p >= 0.99) return "99%+";
  if (p <= 0.01) return "under 1%";
  return `${Math.round(100 * p)}%`;
}

/** Compact money for headlines: 208.1M, 1.93M, 34.2K. Full numbers stay in tables. */
export function money(n: number | null | undefined, symbol = CUSTOMER_CURRENCY): string {
  if (n == null || isNaN(n)) return "–";
  const a = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  let body: string;
  if (a >= 1e9) body = `${(a / 1e9).toFixed(2)}B`;
  else if (a >= 1e6 || Math.round(a / 1e3) >= 1000) body = `${(a / 1e6).toFixed(a < 1e7 ? 2 : 1)}M`;
  else if (a >= 1e3) body = a < 1e5 ? `${(a / 1e3).toFixed(1)}K` : `${(a / 1e3).toFixed(0)}K`;
  else body = fmtMoney(a);
  return `${sign}${symbol}${body}`;
}

/** Full money with symbol, for sentences and tooltips. */
export function moneyFull(n: number | null | undefined, symbol = CUSTOMER_CURRENCY): string {
  return n == null || isNaN(n) ? "–" : `${symbol}${fmtMoney(n)}`;
}

const DRIVERS: Record<string, string> = {
  Age: "Age",
  Balance: "Account balance",
  CreditScore: "Credit score",
  Gender_Female: "Female customer",
  Gender_Male: "Male customer",
  HasCrCard: "Has a credit card",
  IsActiveMember: "Active member",
  NumOfProducts: "Number of products",
  Tenure: "Years as a customer",
  EstimatedSalary: "Estimated salary",
  customer_value: "Estimated salary",
  balance_value_ratio: "Balance compared with salary",
  zero_balance: "No account balance",
};
export function driverLabel(feature: string, fallback = ""): string {
  if (DRIVERS[feature]) return DRIVERS[feature];
  if (feature.startsWith("Geography_")) return `Based in ${feature.slice("Geography_".length)}`;
  const s = (fallback || feature).replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export const MODEL_NAMES: Record<string, string> = {
  logreg_mle: "Logistic regression",
  logreg_map: "Regularised logistic regression",
  naive_bayes: "Naive Bayes",
  random_forest: "Random Forest",
  xgboost: "XGBoost",
  lstm: "Sequence neural network",
};

const pc = (x: number) => `${Math.round(x * 100)}%`;

export const GLOSSARY = {
  revenueAtRisk:
    "The revenue we expect to lose in the next period if nothing is done. It is each customer's value multiplied by their chance of leaving, added up.",
  chance: "The model's estimate of how likely this customer is to cancel in the next period.",
  band: `Customers are grouped by chance of leaving: high is above ${pc(BAND_LIMITS.amberMax)}, medium is between ${pc(BAND_LIMITS.greenMax)} and ${pc(BAND_LIMITS.amberMax)}, low is ${pc(BAND_LIMITS.greenMax)} or below.`,
  group: "Customers the model found to behave alike. The name describes what most of them have in common.",
  saved: "The revenue we expect to keep by spending the budget on the offers shown, compared with doing nothing.",
  returnOnBudget: "Expected revenue saved divided by money spent.",
  prAuc:
    "Precision at top (PR-AUC): how well the model puts customers who really leave at the top of the list. 100% is perfect. The share of leavers is what a random list scores.",
  brier: "Accuracy of the percentages (Brier score): average error of the predicted chances. Lower is better, 0 is perfect.",
  ece: "Calibration gap (ECE): how far the predicted chances are from what really happened. Lower is better. 2% means a customer shown as 30% really leaves between about 28% and 32% of the time.",
  bestReturn: "Spends the budget where each unit of money is expected to keep the most revenue, within a limit per customer.",
  sameAmount: "Gives every customer who gets an offer the same amount of the budget.",
  mostAtRisk: "Gives the largest share of the budget to the customers with the highest chance of leaving.",
} as const;
