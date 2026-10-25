import type { CSSProperties, ReactNode } from "react";
import type { Band } from "../api";
import { BAND_VAR, BAND_WORD } from "../lib/plain";

/** Risk ring: blue lightness shows the band, the word is always printed next to it. `p` is 0 to 1. */
export function RingMini({ p, band, size = 38, stroke = 8, delay = 0, animated = false }: { p: number; band: Band; size?: number; stroke?: number; delay?: number; animated?: boolean }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 100 100" style={{ width: size, height: size, pointerEvents: "none" }}>
      <circle cx="50" cy="50" r="40" fill="none" stroke="rgba(var(--blue-100-rgb), .15)" strokeWidth={stroke} />
      <circle
        className={animated ? "arcSm" : undefined}
        cx="50" cy="50" r="40" fill="none" stroke={BAND_VAR[band]} transform="rotate(-90 50 50)"
        strokeWidth={stroke} strokeLinecap="round" strokeDasharray={`${251.3 * p} 251.3`}
        style={animated ? { animationDelay: `${delay}ms` } : undefined}
      />
    </svg>
  );
}

export function BandTag({ band, size = "sm", style }: { band: Band; size?: "sm" | "md"; style?: CSSProperties }) {
  return (
    <span
      style={{
        fontSize: size === "sm" ? 11 : 12, fontWeight: 500, padding: size === "sm" ? "3px 8px" : "3px 10px", borderRadius: 999,
        color: BAND_VAR[band], background: "rgba(var(--bg-rgb), .55)", border: "1px solid rgba(var(--blue-200-rgb), .18)",
        backdropFilter: "blur(6px)", pointerEvents: "none", ...style,
      }}
    >
      {BAND_WORD[band]}
    </span>
  );
}

export function PosterTexture({ size = 22 }: { size?: number }) {
  return <span aria-hidden="true" className="gridtex" style={{ backgroundSize: `${size}px ${size}px` }} />;
}

export function Skeleton({ w = "100%", h = 16, r = 8, style }: { w?: number | string; h?: number | string; r?: number; style?: CSSProperties }) {
  return <div className="shimmer" aria-hidden="true" style={{ width: w, height: h, borderRadius: r, ...style }} />;
}

export function Arrow({ dir, size = 22 }: { dir: "l" | "r"; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden="true">
      <path d={dir === "l" ? "M10 3L5 8l5 5" : "M6 3l5 5-5 5"} fill="none" stroke="var(--ink)" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function ArrowRight({ stroke = "var(--ink-inverse)", size = 14, w = 1.8 }: { stroke?: string; size?: number; w?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden="true">
      <path d="M3 8h10M9 4l4 4-4 4" fill="none" stroke={stroke} strokeWidth={w} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Message({ children }: { children: ReactNode }) {
  return <p style={{ color: "var(--ink-muted)", padding: "24px 48px" }}>{children}</p>;
}

export const Wordmark = ({ size = 24 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true">
    <circle cx="32" cy="32" r="27" fill="none" stroke="rgba(var(--blue-200-rgb), .25)" strokeWidth={6} />
    <path d="M32 5 A27 27 0 1 1 8.6 45.5" fill="none" stroke="var(--blue-200)" strokeWidth={6} strokeLinecap="round" />
    <circle cx="32" cy="32" r="7" fill="var(--ink)" />
  </svg>
);
