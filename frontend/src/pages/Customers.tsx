import { useCallback, useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { fetchCustomers } from "../api";
import type { Customer } from "../api";
import { pct, short } from "../lib/format";
import { BAND_VAR, customerName, posterFor } from "../lib/plain";
import { useApp } from "../state/app";
import { BandTag, Message, PosterTexture, RingMini, Skeleton } from "../components/bits";
import { tagsFor } from "../components/CardRow";

const PAGE = 48;
const BANDS = [
  { v: "", label: "All" },
  { v: "red", label: "High risk" },
  { v: "amber", label: "Medium risk" },
  { v: "green", label: "Low risk" },
];
const COUNTRIES = ["", "France", "Germany", "Spain"];

function GridCard({ c, k }: { c: Customer; k: number }) {
  const { openProfile } = useApp();
  const name = customerName(c);
  const delay = Math.min(k, 14) * 0.055;
  return (
    <motion.div initial={{ opacity: 0, y: 24, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1], delay }}>
      <div className="gcard" style={{ background: posterFor(c.geography).bg }}>
        <button className="cover" style={{ borderRadius: 14 }} onClick={(e) => openProfile(c.customer_id, e.currentTarget)} aria-label={`Open ${name}`} />
        <PosterTexture size={24} />
        <span style={{ position: "absolute", right: 14, top: 14 }}><RingMini p={c.p_churn_calibrated} band={c.risk_band} size={52} stroke={7} animated delay={delay * 1000} /></span>
        <span style={{ position: "absolute", left: 14, top: 14 }}><BandTag band={c.risk_band} /></span>
        <div style={{ position: "absolute", left: 16, right: 16, bottom: 16, display: "flex", flexDirection: "column", gap: 4, pointerEvents: "none" }}>
          <span style={{ fontWeight: 600, fontSize: 22, lineHeight: "26px", letterSpacing: "-0.03em" }}>{name}</span>
          <span style={{ fontSize: 13, color: "var(--ink-poster)" }}>{c.geography}, {tagsFor(c)}</span>
          <span style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginTop: 4 }}>
            <span style={{ color: "var(--blue-100)", fontWeight: 500 }}>{short(c.estimated_salary)} a year</span>
            <span style={{ color: BAND_VAR[c.risk_band], fontWeight: 600 }}>{pct(c.p_churn_calibrated)}</span>
          </span>
        </div>
        <span className="sheen" />
      </div>
    </motion.div>
  );
}

export default function Customers() {
  const [band, setBand] = useState("");
  const [country, setCountry] = useState("");
  const [active, setActive] = useState("");
  const [products, setProducts] = useState("");
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [items, setItems] = useState<Customer[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [error, setError] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const sentinel = useRef<HTMLDivElement>(null);
  const ctl = useRef<AbortController | null>(null);

  useEffect(() => { const t = window.setTimeout(() => setQ(search.trim()), 250); return () => window.clearTimeout(t); }, [search]);

  const query = useCallback(
    (offset: number) => ({ band, country, search: q, active: active === "" ? undefined : active === "yes", min_products: products ? Number(products) : undefined, limit: PAGE, offset }),
    [band, country, q, active, products],
  );

  // a new filter replaces the list (and restarts the stagger)
  const filterKey = `${band}|${country}|${q}|${active}|${products}`;
  useEffect(() => {
    ctl.current?.abort();
    const c = new AbortController();
    ctl.current = c;
    setTotal(null); setError(false);
    fetchCustomers(query(0), c.signal)
      .then((r) => { setItems(r.items); setTotal(r.total); })
      .catch((e) => { if (e.name !== "AbortError") setError(true); });
    return () => c.abort();
  }, [filterKey, query]);

  const more = useCallback(() => {
    if (loadingMore || total == null || items.length >= total) return;
    setLoadingMore(true);
    fetchCustomers(query(items.length)).then((r) => setItems((cur) => [...cur, ...r.items])).catch(() => setError(true)).finally(() => setLoadingMore(false));
  }, [items.length, total, loadingMore, query]);

  useEffect(() => {
    const el = sentinel.current;
    if (!el || typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver((e) => { if (e[0].isIntersecting) more(); }, { rootMargin: "400px" });
    io.observe(el);
    return () => io.disconnect();
  }, [more]);

  const sel = (label: string, value: string, set: (v: string) => void, opts: { v: string; l: string }[]) => (
    <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12, color: "var(--ink-muted)" }}>
      {label}
      <select className="field" value={value} onChange={(e) => set(e.target.value)} style={{ width: 150, minHeight: 40, padding: "8px 12px" }}>
        {opts.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}
      </select>
    </label>
  );

  return (
    <div style={{ padding: "56px clamp(16px, 3.4vw, 48px)", display: "flex", flexDirection: "column", gap: 28 }}>
      <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", gap: 16, alignItems: "flex-end" }}>
        <div>
          <h1 style={{ fontWeight: 600, fontSize: "clamp(32px, 5vw, 44px)", lineHeight: 1.1, letterSpacing: "-0.04em" }}>Customers</h1>
          <p style={{ margin: "8px 0 0", color: "var(--ink-muted)" }} aria-live="polite">
            {total == null ? "Loading…" : `${total.toLocaleString("en-US")} ${total === 1 ? "customer" : "customers"}, sorted by value at risk`}
          </p>
        </div>
        <div role="group" aria-label="Risk level" style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {BANDS.map((b) => (
            <button key={b.v} className={band === b.v ? "chip on" : "chip"} aria-pressed={band === b.v} onClick={() => setBand(b.v)}>{b.label}</button>
          ))}
        </div>
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 14, alignItems: "flex-end" }}>
        <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12, color: "var(--ink-muted)", flex: "1 1 220px", maxWidth: 360 }}>
          Search by name or ID
          <input className="field" type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="For example Castiglione" autoComplete="off" />
        </label>
        {sel("Country", country, setCountry, COUNTRIES.map((c) => ({ v: c, l: c || "All countries" })))}
        {sel("Account use", active, setActive, [{ v: "", l: "All customers" }, { v: "yes", l: "Active members" }, { v: "no", l: "Inactive members" }])}
        {sel("Bank products", products, setProducts, [{ v: "", l: "Any number" }, { v: "2", l: "2 or more" }, { v: "3", l: "3 or more" }, { v: "4", l: "4" }])}
      </div>

      {error && <Message>Customers could not be loaded. Check that the API is running, then try again.</Message>}
      {total === 0 && !error && <Message>No customer matches these filters.</Message>}
      {total == null && !error && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(250px, 1fr))", gap: 16 }} aria-busy="true">
          {Array.from({ length: 8 }, (_, k) => <Skeleton key={k} h={190} r={14} />)}
        </div>
      )}
      {total != null && total > 0 && (
        <div key={filterKey} style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(min(250px, 100%), 1fr))", gap: 16 }}>
          {items.map((c, k) => <GridCard key={c.customer_id} c={c} k={k < PAGE ? k : 0} />)}
        </div>
      )}
      <div ref={sentinel} aria-hidden="true" style={{ height: 1 }} />
      {loadingMore && <p style={{ color: "var(--ink-muted)", textAlign: "center" }}>Loading more…</p>}
      {total != null && items.length < total && !loadingMore && (
        <div style={{ textAlign: "center" }}><button className="ghost" onClick={more}>Show more customers</button></div>
      )}
    </div>
  );
}
