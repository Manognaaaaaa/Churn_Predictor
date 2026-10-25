const DASH = "–";

/** 198,875 */
export function full(n: number | null | undefined): string {
  return n == null || isNaN(n) ? DASH : Math.round(n).toLocaleString("en-US");
}

/** 1.93M or 250K */
export function short(n: number | null | undefined): string {
  if (n == null || isNaN(n)) return DASH;
  const a = Math.abs(n);
  if (a >= 1e6 || Math.round(a / 1e3) >= 1000) return `${(n / 1e6).toFixed(2)}M`;
  if (a >= 1e3) return `${Math.round(n / 1e3)}K`;
  return String(Math.round(n));
}

/** Chance of leaving: 99%+ at 0.99 or more, otherwise a whole percent. Never 100%. */
export function pct(p: number | null | undefined): string {
  if (p == null || isNaN(p)) return DASH;
  return p >= 0.99 ? "99%+" : `${Math.round(p * 100)}%`;
}

/** 0.676 -> 67.6% (model metrics) */
export function pct1(x: number | null | undefined): string {
  return x == null || isNaN(x) ? DASH : `${(100 * x).toFixed(1)}%`;
}

export function fixed(x: number | null | undefined, d = 4): string {
  return x == null || isNaN(x) ? DASH : x.toFixed(d);
}
