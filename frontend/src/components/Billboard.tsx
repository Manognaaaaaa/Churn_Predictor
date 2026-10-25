import { useEffect, useMemo, useState } from "react";
import type { Customer } from "../api";
import { full, pct } from "../lib/format";
import { BAND_VAR, customerName, possessive, pronoun, posterFor } from "../lib/plain";
import { useApp } from "../state/app";
import { useReducedMotion } from "../hooks/useReducedMotion";
import { useMedia } from "../hooks/useMedia";
import { ArrowRight } from "./bits";

export function storyFor(c: Customer): string {
  const name = customerName(c);
  const n = c.num_products ?? 0;
  const he = pronoun(c);
  if (c.risk_band === "red")
    return `${name} is very likely to leave. ${he} holds ${n} ${n === 1 ? "product" : "products"}${c.active ? "" : " and has not used the account recently"}, putting ${full(c.revenue_at_risk)} of yearly value at risk.`;
  if (c.risk_band === "amber")
    return `${name} could leave. ${he} holds ${n} ${n === 1 ? "product" : "products"}, and ${full(c.revenue_at_risk)} of yearly value is at risk. Worth a call.`;
  return `${name} is stable for now, with ${full(c.revenue_at_risk)} of yearly value at risk. Worth a light-touch check in.`;
}

const TICKS = Array.from({ length: 60 }, (_, k) => {
  const a = (k / 60) * Math.PI * 2;
  const r1 = k % 5 === 0 ? 166 : 170;
  return { x1: 200 + r1 * Math.cos(a), y1: 200 + r1 * Math.sin(a), x2: 200 + 174 * Math.cos(a), y2: 200 + 174 * Math.sin(a) };
});

/** Rotating billboard of the top customers by value at risk (8s each). Pauses on hover, hidden tab, open profile, or the pause button. */
export function Billboard({ items, onBudget }: { items: Customer[]; onBudget: () => void }) {
  const { openProfile, profileId } = useApp();
  const reduced = useReducedMotion();
  const narrow = useMedia("(max-width: 800px)");
  const [i, setI] = useState(0);
  const [hover, setHover] = useState(false);
  const [userPaused, setUserPaused] = useState(false);
  const [hidden, setHidden] = useState(typeof document !== "undefined" && document.hidden);
  const featured = useMemo(() => items.slice(0, 4), [items]);

  useEffect(() => {
    const on = () => setHidden(document.hidden);
    document.addEventListener("visibilitychange", on);
    return () => document.removeEventListener("visibilitychange", on);
  }, []);

  if (!featured.length) return null;
  const f = featured[Math.min(i, featured.length - 1)];
  const paused = hover || userPaused || hidden || !!profileId;
  const poster = posterFor(f.geography);
  const arc = 942.5 * f.p_churn_calibrated;
  const next = () => setI((x) => (x + 1) % featured.length);

  return (
    <section
      aria-roledescription="carousel" aria-label="Customers with the most value at risk"
      onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{ position: "relative", height: narrow ? "auto" : 620, overflow: "hidden", display: narrow ? "flex" : "block", flexDirection: "column", paddingBottom: narrow ? 120 : 0 }}
    >
      <div
        key={`bg${i}`} className="kb"
        style={{ position: "absolute", inset: "-4%", background: `radial-gradient(ellipse 40% 55% at 74% ${narrow ? "70%" : "42%"}, ${poster.glow} 0%, transparent 70%), radial-gradient(ellipse 45% 45% at 10% 90%, rgba(30,58,110,.45) 0%, transparent 65%), var(--bg)` }}
      />
      <div aria-hidden="true" style={{ position: "absolute", inset: 0, backgroundImage: "linear-gradient(var(--grid-line) 1px, transparent 1px), linear-gradient(90deg, var(--grid-line) 1px, transparent 1px)", backgroundSize: "56px 56px", WebkitMaskImage: "radial-gradient(ellipse 60% 70% at 70% 40%, #000 20%, transparent 75%)", maskImage: "radial-gradient(ellipse 60% 70% at 70% 40%, #000 20%, transparent 75%)" }} />
      <div className="drift" style={{ position: narrow ? "relative" : "absolute", order: 2, right: narrow ? undefined : "8%", margin: narrow ? "28px auto 0" : 0, top: narrow ? undefined : 64, width: narrow ? 220 : 420, maxWidth: narrow ? "none" : "38%" }}>
        <svg viewBox="0 0 400 400" aria-hidden="true" style={{ width: "100%", height: "auto", display: "block", overflow: "visible" }}>
          <defs>
            <linearGradient id="ringg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="var(--blue-100)" /><stop offset="1" stopColor="var(--blue-500)" /></linearGradient>
          </defs>
          <g className="orbit"><circle cx="200" cy="200" r="182" fill="none" stroke="rgba(var(--blue-200-rgb), .16)" strokeWidth={1} strokeDasharray="1 7" /><circle cx="200" cy="18" r="3" fill="var(--blue-200)" /></g>
          <circle cx="200" cy="200" r="150" fill="none" stroke="rgba(var(--line-rgb), .12)" strokeWidth={10} />
          <circle key={`arc${i}`} className="arc" cx="200" cy="200" r="150" fill="none" stroke="url(#ringg)" transform="rotate(-90 200 200)" strokeWidth={10} strokeLinecap="round" strokeDasharray={`${arc} 942.5`} />
          {TICKS.map((t, k) => <line key={k} x1={t.x1.toFixed(1)} y1={t.y1.toFixed(1)} x2={t.x2.toFixed(1)} y2={t.y2.toFixed(1)} stroke="rgba(var(--blue-200-rgb), .25)" strokeWidth={1} />)}
        </svg>
        <div key={`pc${i}`} style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 2 }}>
          <div className="tx" style={{ fontWeight: 300, fontSize: narrow ? 44 : 76, lineHeight: narrow ? "48px" : "80px", letterSpacing: "-0.04em" }}>{pct(f.p_churn_calibrated)}</div>
          <div style={{ color: "var(--ink-muted)", fontSize: 13 }}>chance of leaving</div>
        </div>
      </div>
      <div aria-hidden="true" style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: 240, background: "linear-gradient(transparent, var(--bg))" }} />
      <div key={`tx${i}`} aria-live={paused ? "polite" : "off"} style={{ position: narrow ? "relative" : "absolute", left: narrow ? undefined : "clamp(16px, 3.4vw, 48px)", top: narrow ? undefined : 120, padding: narrow ? "56px 16px 0" : 0, maxWidth: 580, order: 1, display: "flex", flexDirection: "column", gap: 18 }}>
        <div className="tx" style={{ display: "inline-flex", alignSelf: "flex-start", alignItems: "center", gap: 8, padding: "5px 12px 5px 8px", borderRadius: 999, border: "1px solid rgba(var(--blue-200-rgb), .25)", background: "rgba(30,58,110,.35)", color: "var(--blue-100)", fontSize: 12, fontWeight: 500 }}>
          <span style={{ width: 6, height: 6, borderRadius: 999, background: "var(--blue-200)", boxShadow: "0 0 10px var(--blue-200)" }} />
          Number {i + 1} in value at risk today
        </div>
        <h1 className="tx" style={{ fontWeight: 600, fontSize: narrow ? 40 : 64, lineHeight: narrow ? "44px" : "66px", letterSpacing: "-0.045em", animationDelay: "80ms" }}>{customerName(f)}</h1>
        <div className="tx" style={{ display: "flex", flexWrap: "wrap", color: "var(--ink-muted)", fontSize: 14, animationDelay: "160ms", rowGap: 4 }}>
          <span style={{ color: "var(--blue-100)", fontWeight: 500, paddingRight: 14 }}>{full(f.estimated_salary)} a year</span>
          <span style={{ padding: "0 14px", borderLeft: "1px solid var(--line-strong)" }}>{f.geography}</span>
          <span style={{ padding: "0 14px", borderLeft: "1px solid var(--line-strong)" }}>Age {f.age}</span>
          <span style={{ paddingLeft: 14, borderLeft: "1px solid var(--line-strong)" }}>{f.tenure} years with the bank</span>
        </div>
        <p className="tx" style={{ fontSize: 17, lineHeight: "27px", color: "var(--ink-soft)", maxWidth: 520, animationDelay: "240ms" }}>{storyFor(f)}</p>
        <div className="tx" style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 4, animationDelay: "320ms" }}>
          <button className="cta" onClick={(e) => openProfile(f.customer_id, e.currentTarget)}>Open profile <ArrowRight /></button>
          <button className="cta2" onClick={onBudget}>Plan the budget</button>
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 22, alignItems: "center" }}>
          <div role="tablist" aria-label="Featured customers" style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {featured.map((c, k) => (
            <button
              key={c.customer_id} role="tab" aria-selected={k === i} aria-label={`Show ${customerName(c)}`} onClick={() => setI(k)}
              style={{ width: 48, height: 24, border: 0, padding: "10px 0", background: "transparent", cursor: "pointer", borderRadius: 4 }}
            >
              <span style={{ display: "block", height: 3, borderRadius: 2, background: "rgba(var(--line-rgb), .22)", overflow: "hidden" }}>
                {k < i || reduced ? (
                  <span style={{ display: "block", height: "100%", width: k <= i ? "100%" : 0, background: "var(--blue-100)" }} />
                ) : k === i ? (
                  <span key={`p${i}`} className={`pr${paused ? " paused" : ""}`} onAnimationEnd={next} style={{ display: "block", height: "100%", width: "100%", background: "var(--blue-100)" }} />
                ) : null}
              </span>
            </button>
          ))}
          </div>
          <span style={{ fontSize: 12, color: "var(--ink-faint)", marginLeft: 6 }}>{i + 1} of {featured.length}</span>
          {!reduced && (
            <button className="round" onClick={() => setUserPaused((p) => !p)} aria-pressed={userPaused} aria-label={userPaused ? "Resume rotation" : "Pause rotation"} style={{ marginLeft: 4 }}>
              <svg width="10" height="10" viewBox="0 0 16 16" aria-hidden="true">
                {userPaused ? <path d="M4 2l10 6-10 6z" fill="var(--ink)" /> : <path d="M4 2h3v12H4zM9 2h3v12H9z" fill="var(--ink)" />}
              </svg>
            </button>
          )}
        </div>
      </div>
    </section>
  );
}
