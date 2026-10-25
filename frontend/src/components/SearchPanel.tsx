import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { fetchCustomers } from "../api";
import type { Customer } from "../api";
import { BAND_VAR, BAND_WORD, customerName } from "../lib/plain";
import { useApp } from "../state/app";

function Highlight({ text, q }: { text: string; q: string }) {
  const i = q ? text.toLowerCase().indexOf(q.toLowerCase()) : -1;
  if (i < 0) return <>{text}</>;
  return (
    <>
      {text.slice(0, i)}
      <mark style={{ background: "rgba(var(--blue-500-rgb), .35)", color: "var(--blue-100)", borderRadius: 3 }}>{text.slice(i, i + q.length)}</mark>
      {text.slice(i + q.length)}
    </>
  );
}

/** Jump to any customer from any page: filters on the server as you type, Enter opens the profile, Escape closes. */
export function SearchPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { openProfile } = useApp();
  const [q, setQ] = useState("");
  const [items, setItems] = useState<Customer[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [active, setActive] = useState(0);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    const ctl = new AbortController();
    const t = window.setTimeout(() => {
      fetchCustomers({ search: q.trim(), limit: 8 }, ctl.signal)
        .then((r) => { setItems(r.items); setActive(0); setLoaded(true); })
        .catch(() => { /* aborted or offline: keep the last list */ });
    }, q ? 200 : 0);
    return () => { window.clearTimeout(t); ctl.abort(); };
  }, [q, open]);

  useEffect(() => {
    if (open) window.setTimeout(() => input.current?.focus(), 60);
    else setQ("");
  }, [open]);

  const pick = (c: Customer) => { onClose(); openProfile(c.customer_id); };

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            key="bd" onClick={onClose} aria-hidden="true"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.25 }}
            style={{ position: "fixed", inset: 0, zIndex: 50, background: "rgba(3,6,13,.6)" }}
          />
          <motion.div
            key="panel" role="dialog" aria-label="Search customers"
            initial={{ opacity: 0, y: -8, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -8, scale: 0.97 }}
            transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
            style={{ position: "fixed", zIndex: 51, top: 68, left: "50%", marginLeft: "calc(min(560px, 92vw) / -2)", width: "min(560px, 92vw)", transformOrigin: "top center", background: "var(--bg-raised)", border: "1px solid var(--line-strong)", borderRadius: 12, boxShadow: "0 24px 48px -16px rgba(0,0,0,.6)" }}
            onKeyDown={(e) => {
              if (e.key === "Escape") { e.stopPropagation(); onClose(); }
              if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(items.length - 1, a + 1)); }
              if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(0, a - 1)); }
              if (e.key === "Enter" && items[active]) pick(items[active]);
            }}
          >
            <label htmlFor="searchq" style={{ position: "absolute", left: -9999 }}>Search by name or ID</label>
            <input
              id="searchq" ref={input} type="search" value={q} onChange={(e) => setQ(e.target.value)} autoComplete="off"
              placeholder="Type a name or customer ID"
              style={{ font: "inherit", width: "100%", boxSizing: "border-box", padding: "14px 16px", minHeight: 52, border: 0, borderBottom: "1px solid var(--line)", background: "transparent", color: "var(--ink)", borderRadius: "12px 12px 0 0" }}
            />
            <div role="listbox" aria-label="Matching customers" style={{ padding: 6, maxHeight: 340, overflowY: "auto" }}>
              {items.map((c, k) => {
                const name = customerName(c);
                return (
                  <button
                    key={c.customer_id} role="option" aria-selected={k === active} onClick={() => pick(c)} onMouseEnter={() => setActive(k)}
                    style={{ width: "100%", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, textAlign: "left", minHeight: 48, padding: "8px 12px", border: 0, borderRadius: 8, cursor: "pointer", background: k === active ? "rgba(var(--blue-500-rgb), .18)" : "transparent", color: "var(--ink)" }}
                  >
                    <span style={{ display: "flex", flexDirection: "column" }}>
                      <span style={{ fontWeight: 500 }}><Highlight text={name} q={q.trim()} /></span>
                      <span style={{ fontSize: 12, color: "var(--ink-faint)" }}>
                        {c.geography ? `${c.geography}, ` : ""}ID <Highlight text={c.customer_id} q={q.trim()} />
                      </span>
                    </span>
                    <span style={{ fontSize: 12, color: BAND_VAR[c.risk_band] }}>{BAND_WORD[c.risk_band]}</span>
                  </button>
                );
              })}
              {loaded && items.length === 0 && <div style={{ padding: "10px 12px", color: "var(--ink-muted)" }}>No customer matches.</div>}
              {!loaded && <div style={{ padding: "10px 12px", color: "var(--ink-muted)" }}>Searching…</div>}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
