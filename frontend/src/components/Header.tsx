import { motion } from "framer-motion";
import { Wordmark } from "./bits";

export type Screen = "home" | "customers" | "budget" | "model";
const NAVS: { key: Screen; label: string }[] = [
  { key: "home", label: "Home" },
  { key: "customers", label: "Customers" },
  { key: "budget", label: "Retention budget" },
  { key: "model", label: "Model" },
];

interface Props {
  screen: Screen;
  onScreen: (s: Screen) => void;
  trainedAt: string | null | undefined;
  onSearch: () => void;
  onReplay: () => void;
}

export function Header({ screen, onScreen, trainedAt, onSearch, onReplay }: Props) {
  const updated = trainedAt ? new Date(trainedAt).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : null;
  return (
    <header
      style={{ position: "sticky", top: 0, zIndex: 30, display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 12, padding: "0 clamp(16px, 3.4vw, 48px)", background: "rgba(var(--bg-rgb), .72)", backdropFilter: "blur(16px) saturate(140%)", WebkitBackdropFilter: "blur(16px) saturate(140%)", borderBottom: "1px solid rgba(var(--line-rgb), .10)" }}
    >
      <div className="hdr-left">
        <div className="hdr-logo" style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Wordmark />
          <span style={{ fontWeight: 600, fontSize: 15, letterSpacing: "-0.01em" }}>Churn &amp; Revenue Risk</span>
        </div>
        <nav aria-label="Main" className="hdr-nav">
          {NAVS.map((n) => (
            <button key={n.key} className={screen === n.key ? "nav on" : "nav"} aria-current={screen === n.key ? "page" : undefined} onClick={() => onScreen(n.key)}>
              {n.label}
              {screen === n.key && <motion.span layoutId="nav-underline" className="nav-underline" aria-hidden="true" transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }} />}
            </button>
          ))}
        </nav>
      </div>
      <div className="hdr-right">
        {updated && <span className="hdr-updated" style={{ fontSize: 12, color: "var(--ink-faint)" }}>Model updated {updated}</span>}
        <button className="ghost" onClick={onSearch} aria-label="Search customers (Ctrl K)">
          <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true"><circle cx="7" cy="7" r="5" fill="none" stroke="currentColor" strokeWidth="1.6" /><path d="M11 11l3.5 3.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>
          Search
        </button>
        <button className="ghost" onClick={onReplay}>Replay intro</button>
      </div>
    </header>
  );
}
