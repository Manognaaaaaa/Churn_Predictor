import { useEffect, useRef, useState } from "react";
import type { Customer } from "../api";
import { pct, short } from "../lib/format";
import { BAND_VAR, BAND_WORD, customerName, posterFor } from "../lib/plain";
import { useMedia } from "../hooks/useMedia";
import { useApp } from "../state/app";
import { Arrow, BandTag, PosterTexture, RingMini } from "./bits";

export function tagsFor(c: Customer): string {
  const n = c.num_products ?? 0;
  return [`${n} product${n === 1 ? "" : "s"}`, c.active ? "Active" : "Inactive", `Age ${c.age ?? "–"}`].join(", ");
}

function PlusIcon({ done }: { done: boolean }) {
  return (
    <svg width="10" height="10" viewBox="0 0 16 16" aria-hidden="true">
      <path d={done ? "M3 8.5l3.2 3.2L13 4.5" : "M8 2v12M2 8h12"} fill="none" stroke="var(--ink)" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function RowCard({ c, k, per, rank }: { c: Customer; k: number; per: number; rank: number | null }) {
  const { openProfile, shortlist, toggleShortlist } = useApp();
  const name = customerName(c);
  const poster = posterFor(c.geography);
  const listed = shortlist.includes(c.customer_id);
  const origin = k % per === 0 ? "left center" : k % per === per - 1 ? "right center" : "center center";
  return (
    <div className="cardwrap">
      {rank != null && <span className="num" aria-hidden="true">{rank}</span>}
      <div className="tile" style={{ transformOrigin: origin, marginLeft: rank != null ? (per === 2 ? "16%" : "28%") : 0, background: poster.bg }}>
        <button className="cover" onClick={(e) => openProfile(c.customer_id, e.currentTarget)} aria-label={`Open ${name}`} />
        <PosterTexture />
        <span style={{ position: "absolute", right: 10, top: 10 }}><RingMini p={c.p_churn_calibrated} band={c.risk_band} size={38} /></span>
        <span style={{ position: "absolute", left: 12, top: 12 }}><BandTag band={c.risk_band} /></span>
        <span style={{ position: "absolute", left: 12, bottom: 14, display: "flex", flexDirection: "column", pointerEvents: "none" }}>
          <span style={{ fontWeight: 600, fontSize: "clamp(13px, 1.4vw, 17px)", lineHeight: "20px", letterSpacing: "-0.02em" }}>{name}</span>
          <span style={{ fontSize: 12, color: "var(--ink-poster)" }}>{c.geography}</span>
        </span>
        <span aria-hidden="true" style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: 2, background: "rgba(var(--line-rgb), .18)" }}>
          <span style={{ display: "block", height: "100%", width: `${Math.round(c.p_churn_calibrated * 100)}%`, background: BAND_VAR[c.risk_band] }} />
        </span>
        <span className="sheen" />
        <div className="info">
          <div style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 7 }}>
            <button className="round solid" onClick={(e) => openProfile(c.customer_id, e.currentTarget)} aria-label={`Open ${name}`}>
              <svg width="10" height="10" viewBox="0 0 16 16" aria-hidden="true"><path d="M3 8h10M9 4l4 4-4 4" fill="none" stroke="var(--ink-inverse)" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" /></svg>
            </button>
            <button className="round" onClick={() => toggleShortlist(c)} aria-pressed={listed} aria-label={listed ? `Remove ${name} from the offer list` : `Add ${name} to the offer list`}>
              <PlusIcon done={listed} />
            </button>
            <span style={{ marginLeft: "auto", fontSize: 11, fontWeight: 600, color: BAND_VAR[c.risk_band] }}>{pct(c.p_churn_calibrated)} chance of leaving</span>
          </div>
          <div style={{ fontSize: 11, lineHeight: "15px", color: "var(--ink-soft)" }}>{tagsFor(c)}</div>
          <div style={{ fontSize: 11, lineHeight: "15px", color: "var(--blue-100)", fontWeight: 500 }}>{short(c.estimated_salary)} a year · {BAND_WORD[c.risk_band]}</div>
        </div>
      </div>
    </div>
  );
}

/** A titled row of customer cards. Desktop: one page (5 cards) per arrow click. Phone: native swipe, 2 cards. */
export function CardRow({ title, count, items, ranked = false, delay = 0 }: { title: string; count: number; items: Customer[]; ranked?: boolean; delay?: number }) {
  const narrow = useMedia("(max-width: 700px)");
  const wide = useMedia("(min-width: 1250px)");
  const mid = useMedia("(min-width: 900px)");
  const per = narrow ? 2 : wide ? 5 : mid ? 4 : 3;
  const pages = Math.max(1, Math.ceil(items.length / per));
  const [off, setOff] = useState(0);
  const page = Math.min(off, pages - 1);
  const wrap = useRef<HTMLElement>(null);
  const [seen, setSeen] = useState(false);

  useEffect(() => {
    const el = wrap.current;
    if (!el || typeof IntersectionObserver === "undefined") { setSeen(true); return; }
    const io = new IntersectionObserver((e) => { if (e[0].isIntersecting) { setSeen(true); io.disconnect(); } }, { rootMargin: "200px" });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  // render the visible page and the next one only (cards before them are needed for the slide offset)
  const shown = narrow ? items : items.slice(0, (page + 2) * per);
  return (
    <section ref={wrap} className="rowwrap" style={{ animation: "scrIn .7s var(--ease) both", animationDelay: `${delay}ms`, ["--per" as string]: per, ["--cw" as string]: narrow ? "calc((100vw - 44px) / 2)" : undefined }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 14, padding: "0 clamp(16px, 3.4vw, 48px)" }}>
        <h2 style={{ fontSize: 18, lineHeight: "26px", fontWeight: 600, letterSpacing: "-0.02em" }}>{title}</h2>
        <span className="more" style={{ fontSize: 13, color: "var(--blue-200)" }}>{count.toLocaleString("en-US")} customers</span>
        {!narrow && pages > 1 && (
          <span style={{ marginLeft: "auto", display: "flex", gap: 4 }} aria-hidden="true">
            {Array.from({ length: pages }, (_, k) => (
              <span key={k} style={{ width: 14, height: 2, borderRadius: 2, background: k === page ? "var(--blue-100)" : "rgba(var(--line-rgb), .25)", transition: "background .4s" }} />
            ))}
          </span>
        )}
      </div>
      <div style={{ position: "relative" }}>
        {!narrow && (
          <>
            <button className="arrow l" aria-label={`${title}: previous`} onClick={() => setOff(Math.max(0, page - 1))} disabled={page === 0}><Arrow dir="l" /></button>
            <button className="arrow r" aria-label={`${title}: next`} onClick={() => setOff(Math.min(pages - 1, page + 1))} disabled={page >= pages - 1}><Arrow dir="r" /></button>
          </>
        )}
        <div style={{ overflowX: narrow ? "auto" : "hidden", overflowY: narrow ? "hidden" : "hidden", padding: narrow ? "30px 16px" : "30px clamp(16px, 3.4vw, 48px)", minHeight: 170, scrollSnapType: narrow ? "x mandatory" : undefined }}>
          <div className="track" style={{ transform: narrow ? "none" : `translateX(calc(${page} * -1 * (100% + 12px)))` }}>
            {seen && shown.map((c, k) => <RowCard key={c.customer_id} c={c} k={k} per={per} rank={ranked ? k + 1 : null} />)}
          </div>
        </div>
      </div>
    </section>
  );
}
