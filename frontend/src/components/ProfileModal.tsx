import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useCustomer, useProductRates, useRates } from "../api";
import type { CustomerDetail, Driver, ProductRate, Rates } from "../api";
import { full, pct } from "../lib/format";
import { BAND_VAR, BAND_WORD, customerName, featureLabel, initials, offerDesc, offerLabel, posterFor } from "../lib/plain";
import { useApp } from "../state/app";
import { BandTag, Skeleton } from "./bits";
import { storyFor } from "./Billboard";

const EASE = [0.22, 1, 0.36, 1] as const;

function Gauge({ p, was, band }: { p: number; was: number | null; band: CustomerDetail["risk_band"] }) {
  return (
    <div>
      <svg viewBox="0 0 260 150" aria-hidden="true" style={{ width: "100%", maxWidth: 300, height: "auto", display: "block" }}>
        <defs>
          <linearGradient id="gg" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stopColor="var(--blue-500)" /><stop offset="1" stopColor="var(--blue-100)" /></linearGradient>
        </defs>
        <path d="M20 130 A110 110 0 0 1 240 130" fill="none" stroke="rgba(var(--line-rgb), .14)" strokeWidth={10} strokeLinecap="round" />
        <path d="M20 130 A110 110 0 0 1 240 130" fill="none" stroke="url(#gg)" strokeWidth={10} strokeLinecap="round" strokeDasharray={`${345.6 * p} 400`} style={{ transition: "stroke-dasharray 1.2s var(--ease)" }} />
        <g style={{ transformOrigin: "130px 130px", transform: `rotate(${-90 + 180 * p}deg)`, transition: "transform 1.4s var(--spring)" }}>
          <line x1="130" y1="130" x2="130" y2="44" stroke="var(--ink)" strokeWidth={2} strokeLinecap="round" />
        </g>
        <circle cx="130" cy="130" r="7" fill="var(--ink)" />
        <circle cx="130" cy="130" r="3" fill="var(--bg-raised)" />
      </svg>
      <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
        <span style={{ fontWeight: 300, fontSize: 48, lineHeight: "52px", letterSpacing: "-0.045em" }} aria-label={`${pct(p)} chance of leaving`}>{pct(p)}</span>
        <span style={{ fontSize: 13, color: "var(--ink-muted)" }}>chance of leaving {was != null && `(was ${pct(was)})`}</span>
        <span style={{ fontSize: 12, color: BAND_VAR[band] }}>{BAND_WORD[band]}</span>
      </div>
    </div>
  );
}

const TILE_FEATURES: Record<string, string[]> = {
  value: ["customer_value", "balance_value_ratio"],
  balance: ["Balance", "zero_balance", "balance_value_ratio"],
  products: ["NumOfProducts"],
  credit: ["CreditScore"],
  active: ["IsActiveMember"],
  years: ["Tenure"],
};

/** One plain sentence under a driver, quoting the real leaving rate in the data when we have one. */
function driverNote(d: Driver, c: CustomerDetail, products: ProductRate[] | undefined, rates: Rates | undefined): string | null {
  const rate = (n: number, left: number, total: number, what: string) =>
    left === total ? `All ${full(total)} customers ${what} left the bank.` : `${full(left)} of ${full(total)} customers ${what} left the bank (${Math.round((left / total) * 100)}%).`;
  const v = d.value == null ? null : Math.round(d.value);
  if (d.feature === "NumOfProducts" && v != null) {
    const r = products?.find((x) => x.num_products === v);
    return r ? rate(v, r.left, r.customers, `with ${v} ${v === 1 ? "product" : "products"}`) : null;
  }
  if (!rates) return null;
  const find = (rows: Rates["geography"], key: string) => rows.find((x) => x.key === key);
  if (d.feature === "IsActiveMember" && v != null) {
    const r = find(rates.active, String(v));
    return r ? `${Math.round(r.rate * 100)}% of ${v ? "active" : "inactive"} members left the bank.` : null;
  }
  if (d.feature.startsWith("Geography_")) {
    const country = d.feature.slice(10);
    const r = find(rates.geography, country);
    return r ? `${Math.round(r.rate * 100)}% of customers based in ${country} left the bank.` : null;
  }
  const bandRow = (rows: Rates["age_band"], age: number | null, edges: number[], names: string[]) => {
    if (age == null) return null;
    let k = 0;
    while (k < edges.length && age >= edges[k]) k++;
    return rows.find((x) => x.key === names[k]);
  };
  if (d.feature === "Age" && v != null) {
    const r = bandRow(rates.age_band, v, [30, 40, 50, 60], ["under 30", "30s", "40s", "50s", "60 and over"]);
    return r ? `${Math.round(r.rate * 100)}% of customers in their ${r.key === "under 30" ? "twenties and younger" : r.key === "60 and over" ? "sixties and older" : r.key} left the bank.` : null;
  }
  if (d.feature === "Tenure" && v != null) {
    const r = bandRow(rates.tenure_band, v, [3, 6, 9], ["0-2 years", "3-5 years", "6-8 years", "9 years or more"]);
    return r ? `${Math.round(r.rate * 100)}% of customers with ${r.key} at the bank left.` : null;
  }
  if (d.feature === "CreditScore" && v != null) {
    const r = bandRow(rates.credit_band, v, [500, 600, 700], ["under 500", "500-599", "600-699", "700 or more"]);
    return r ? `${Math.round(r.rate * 100)}% of customers with a credit score ${r.key} left the bank.` : null;
  }
  return null;
}

function Content({ d }: { d: CustomerDetail }) {
  const { toast, logSent, closeProfile } = useApp();
  const products = useProductRates();
  const rates = useRates();
  const [offerIdx, setOfferIdx] = useState(-1);
  const name = customerName(d);
  const poster = posterFor(d.geography);
  const offer = offerIdx >= 0 ? d.offers[offerIdx] : null;
  const p = offer ? offer.new_p_churn : d.p_churn_calibrated;
  const band = p >= 0.5 ? "red" : p >= 0.25 ? "amber" : "green";
  const driverMax = Math.max(1e-9, ...d.top_drivers.map((x) => Math.abs(x.contribution)));
  const risky = useMemo(() => {
    const raising = new Set(d.top_drivers.filter((x) => x.contribution > 0).map((x) => x.feature));
    return (tile: string) => TILE_FEATURES[tile].some((f) => raising.has(f));
  }, [d.top_drivers]);
  const facts: [string, string, string][] = [
    ["Yearly value", full(d.estimated_salary), "value"],
    ["Balance", full(d.balance), "balance"],
    ["Products", String(d.num_products ?? "–"), "products"],
    ["Credit score", String(d.credit_score ?? "–"), "credit"],
    ["Active", d.active ? "Yes" : "No", "active"],
    ["Years", String(d.tenure ?? "–"), "years"],
  ];

  return (
    <>
      <div style={{ position: "relative", height: 280, overflow: "hidden", borderRadius: "18px 18px 0 0" }}>
        <div className="kb" style={{ position: "absolute", inset: "-4%", background: poster.bg }} />
        <div aria-hidden="true" style={{ position: "absolute", inset: 0, backgroundImage: "linear-gradient(rgba(var(--blue-100-rgb), .05) 1px, transparent 1px), linear-gradient(90deg, rgba(var(--blue-100-rgb), .05) 1px, transparent 1px)", backgroundSize: "40px 40px", WebkitMaskImage: "radial-gradient(ellipse at 80% 20%, #000, transparent 70%)", maskImage: "radial-gradient(ellipse at 80% 20%, #000, transparent 70%)" }} />
        <div aria-hidden="true" style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: 170, background: "linear-gradient(transparent, var(--bg-raised))" }} />
        <button className="round" onClick={closeProfile} aria-label="Close" style={{ position: "absolute", right: 18, top: 18, width: 44, height: 44 }} data-autofocus>
          <svg width="12" height="12" viewBox="0 0 16 16" aria-hidden="true"><path d="M3 3l10 10M13 3L3 13" stroke="var(--ink)" strokeWidth={1.8} strokeLinecap="round" /></svg>
        </button>
        <div style={{ position: "absolute", left: "clamp(16px, 4vw, 36px)", right: 16, bottom: 26, display: "flex", flexDirection: "column", gap: 10 }}>
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, ease: EASE }} style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            <BandTag band={d.risk_band} size="md" />
            {d.exited === 1 && <span style={{ fontSize: 12, color: "var(--ink-muted)" }}>Left the bank in the data</span>}
          </motion.div>
          <motion.h2 id="profile-title" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, ease: EASE, delay: 0.08 }} style={{ fontWeight: 600, fontSize: "clamp(34px, 6vw, 50px)", lineHeight: 1.08, letterSpacing: "-0.045em" }}>{name}</motion.h2>
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, ease: EASE, delay: 0.16 }} style={{ display: "flex", flexWrap: "wrap", color: "var(--ink-muted)", fontSize: 14, rowGap: 4 }}>
            <span style={{ color: "var(--blue-100)", fontWeight: 500, paddingRight: 12 }}>{full(d.estimated_salary)} a year</span>
            <span style={{ padding: "0 12px", borderLeft: "1px solid var(--line-strong)" }}>{d.geography}</span>
            <span style={{ padding: "0 12px", borderLeft: "1px solid var(--line-strong)" }}>Age {d.age}</span>
            <span style={{ padding: "0 12px", borderLeft: "1px solid var(--line-strong)" }}>{d.tenure} years</span>
            <span style={{ paddingLeft: 12, borderLeft: "1px solid var(--line-strong)" }}>ID {d.customer_id}</span>
          </motion.div>
        </div>
      </div>

      <div style={{ padding: "12px clamp(16px, 4vw, 36px) 36px", display: "flex", flexWrap: "wrap", gap: 32 }}>
        <div style={{ flex: "1 1 300px", display: "flex", flexDirection: "column", gap: 12, minWidth: 0 }}>
          <Gauge p={p} band={band} was={offer ? d.p_churn_calibrated : null} />
          <div style={{ fontSize: 13, color: "var(--ink-muted)", marginTop: 4 }}>Try an offer (estimated effect)</div>
          {d.offers.length === 0 && <p style={{ fontSize: 14, color: "var(--ink-muted)" }}>No retention offer fits this customer.</p>}
          {d.offers.map((o, k) => (
            <motion.button
              key={o.offer} className={offerIdx === k ? "offer on" : "offer"} aria-pressed={offerIdx === k} onClick={() => setOfferIdx(offerIdx === k ? -1 : k)}
              initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, ease: EASE, delay: 0.3 + k * 0.08 }}
            >
              <span style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
                <span style={{ fontWeight: 500, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                  {offerLabel(o.offer)}
                  {o.best && <span style={{ fontSize: 11, fontWeight: 600, padding: "2px 8px", borderRadius: 999, background: "rgba(var(--blue-500-rgb), .3)", color: "var(--blue-100)" }}>Best value</span>}
                </span>
                <span style={{ fontSize: 12, color: "var(--ink-muted)" }}>{offerDesc(o.offer, d)}</span>
                <span style={{ fontSize: 12, color: "var(--ink-muted)" }}>Costs {full(o.cost)}, keeps about {full(o.value_kept)}</span>
              </span>
              <span style={{ fontWeight: 500, color: "var(--blue-100)", whiteSpace: "nowrap" }}>{pct(o.new_p_churn)}</span>
            </motion.button>
          ))}
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 4 }}>
            <button
              className="cta"
              onClick={async () => {
                const saved = await logSent({ id: d.customer_id, offer: offer?.offer ?? null });
                toast(`${offer ? offerLabel(offer.offer) : "Offer"} recorded for ${name}.${saved ? "" : " The server could not be reached, so it is saved in this browser only."}`);
              }}
            >
              Send offer
            </button>
            <a className="ghost" href={`/customers/${d.customer_id}/report.pdf`} target="_blank" rel="noopener noreferrer" style={{ textDecoration: "none" }}>Download PDF report</a>
          </div>
        </div>

        <div style={{ flex: "1.2 1 340px", display: "flex", flexDirection: "column", gap: 18, minWidth: 0 }}>
          <p style={{ fontSize: 16, lineHeight: "26px", color: "var(--ink-soft)" }}>{storyFor(d)}</p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 10 }}>
            {facts.map(([label, value, tile], k) => (
              <motion.div
                key={label} className="panel" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, ease: EASE, delay: 0.28 + k * 0.05 }}
                style={{ borderRadius: 12, padding: "12px 14px" }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "var(--ink-muted)" }}>
                  <span aria-hidden="true" title={risky(tile) ? "Raises this customer's risk" : undefined} style={{ width: 6, height: 6, borderRadius: 999, background: risky(tile) ? "var(--blue-100)" : "rgba(var(--line-rgb), .35)", boxShadow: risky(tile) ? "0 0 8px var(--blue-200)" : undefined }} />
                  {label}
                  {risky(tile) && <span className="sr-only">Risk factor</span>}
                </div>
                <div style={{ fontSize: 22, fontWeight: 500, letterSpacing: "-0.03em" }}>{value}</div>
              </motion.div>
            ))}
          </div>
          <div style={{ fontSize: 13, color: "var(--ink-muted)" }}>Why the model flags them</div>
          {d.top_drivers.map((x, k) => {
            const up = x.contribution > 0;
            const note = driverNote(x, d, products.data?.by_products, rates.data);
            return (
              <motion.div key={x.feature} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, ease: EASE, delay: 0.45 + k * 0.11 }} style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 10, fontSize: 14 }}>
                  <span>{featureLabel(x.feature, x.value)}</span>
                  <span style={{ fontSize: 12, color: up ? "var(--blue-100)" : "var(--blue-400)", whiteSpace: "nowrap" }}>{up ? "Raises risk" : "Lowers risk"}</span>
                </div>
                <div style={{ height: 4, borderRadius: 999, background: "var(--track)", overflow: "hidden" }}>
                  <div className="grow" style={{ height: "100%", borderRadius: 999, width: `${(Math.abs(x.contribution) / driverMax) * 100}%`, background: up ? "linear-gradient(90deg, var(--blue-500), var(--blue-100))" : "var(--bar-low)", animationDelay: `${450 + k * 110}ms` }} />
                </div>
                {note && <div style={{ fontSize: 12, color: "var(--ink-muted)" }}>{note}</div>}
              </motion.div>
            );
          })}
        </div>
      </div>
    </>
  );
}

/** Customer profile dialog. Opens from any card, the billboard or search. Traps focus, closes on Escape or a backdrop click. */
export function ProfileModal() {
  const { profileId, closeProfile, returnFocus } = useApp();
  const detail = useCustomer(profileId);
  const panel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!profileId) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.stopPropagation(); closeProfile(); return; }
      if (e.key !== "Tab" || !panel.current) return;
      const f = Array.from(panel.current.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), input, select, [tabindex]:not([tabindex="-1"])')).filter((el) => el.offsetParent !== null);
      if (!f.length) return;
      const first = f[0], last = f[f.length - 1];
      if (e.shiftKey && (document.activeElement === first || !panel.current.contains(document.activeElement))) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", onKey, true);
    const t = window.setTimeout(() => (panel.current?.querySelector<HTMLElement>("[data-autofocus]") ?? panel.current)?.focus(), 80);
    return () => { document.body.style.overflow = prev; document.removeEventListener("keydown", onKey, true); window.clearTimeout(t); };
  }, [profileId, closeProfile, detail.data]);

  return (
    <AnimatePresence onExitComplete={returnFocus}>
      {profileId && (
        <>
          <motion.div key="bd" onClick={closeProfile} aria-hidden="true" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.35 }}
            style={{ position: "fixed", inset: 0, zIndex: 40, background: "rgba(3,6,13,.72)", backdropFilter: "blur(8px)", WebkitBackdropFilter: "blur(8px)" }} />
          <motion.div
            key="panel" ref={panel} role="dialog" aria-modal="true" aria-labelledby="profile-title" tabIndex={-1} className="modal-panel"
            initial={{ opacity: 0, y: 28, scale: 0.96 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 16, scale: 0.98 }}
            transition={{ duration: 0.6, ease: EASE }}
            style={{ position: "fixed", zIndex: 41, left: "50%", top: 32, width: "min(940px, 94vw)", marginLeft: "calc(min(940px, 94vw) / -2)", maxHeight: "calc(100vh - 64px)", overflowY: "auto", background: "var(--bg-raised)", borderRadius: 18, boxShadow: "0 50px 100px -30px rgba(0,0,0,.9), 0 0 0 1px rgba(var(--blue-200-rgb), .14)" }}
          >
            {detail.data ? (
              <Content key={detail.data.customer_id} d={detail.data} />
            ) : (
              <div style={{ padding: 36, display: "flex", flexDirection: "column", gap: 16 }}>
                <h2 id="profile-title" style={{ position: "absolute", left: -9999 }}>Customer profile</h2>
                <button className="round" onClick={closeProfile} aria-label="Close" style={{ alignSelf: "flex-end", width: 44, height: 44 }} data-autofocus>
                  <svg width="12" height="12" viewBox="0 0 16 16" aria-hidden="true"><path d="M3 3l10 10M13 3L3 13" stroke="var(--ink)" strokeWidth={1.8} strokeLinecap="round" /></svg>
                </button>
                {detail.error ? <p style={{ color: "var(--ink-muted)" }}>This customer could not be loaded.</p> : (<><Skeleton w={260} h={50} /><Skeleton w="70%" h={18} /><Skeleton h={160} r={12} /></>)}
              </div>
            )}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
