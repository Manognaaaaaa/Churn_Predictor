const DASH = "–";

/** Thousands separators, no decimals by default. */
export function fmtMoney(x: number | null | undefined, digits = 0): string {
  if (x == null || isNaN(x)) return DASH;
  return x.toLocaleString("en-US", { maximumFractionDigits: digits });
}

/** Fraction (0.676) to one-decimal percent ("67.6%"). */
export function fmtPct(x: number | null | undefined): string {
  return x == null || isNaN(x) ? DASH : `${(100 * x).toFixed(1)}%`;
}

/** Brier / ECE style metrics: four decimals. */
export function fmtMetric(x: number | null | undefined, digits = 4): string {
  return x == null || isNaN(x) ? DASH : x.toFixed(digits);
}
