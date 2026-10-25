import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { usePortfolio } from "../api";
import type { Customer } from "../api";
import { customerName, segmentLabeler } from "../lib/plain";

interface Toast { msg: string; key: number }
interface Ctx {
  profileId: string | null;
  openProfile: (id: string, origin?: Element | null) => void;
  closeProfile: () => void;
  toast: (msg: string) => void;
  toastState: Toast | null;
  shortlist: string[];
  toggleShortlist: (c: Customer) => void;
  logSent: (entry: { id: string; offer: string | null }) => void;
  segLabel: (raw: string | null | undefined) => string;
  returnFocus: () => void;
}

const AppContext = createContext<Ctx | null>(null);

function readList(key: string): string[] {
  try {
    const v = JSON.parse(localStorage.getItem(key) ?? "[]");
    return Array.isArray(v) ? v : [];
  } catch {
    return [];
  }
}
function writeList(key: string, v: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(v));
  } catch {
    /* storage blocked: state lasts for this visit only */
  }
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [profileId, setProfileId] = useState<string | null>(null);
  const origin = useRef<HTMLElement | null>(null);
  const [toastState, setToast] = useState<Toast | null>(null);
  const toastTimer = useRef<number>();
  const [shortlist, setShortlist] = useState<string[]>(() => readList("shortlist"));
  const portfolio = usePortfolio();
  const qc = useQueryClient();

  const segLabel = useMemo(() => segmentLabeler((portfolio.data?.by_segment ?? []).map((s) => s.segment_name)), [portfolio.data]);

  const toast = useCallback((msg: string) => {
    window.clearTimeout(toastTimer.current);
    setToast({ msg, key: Date.now() });
    toastTimer.current = window.setTimeout(() => setToast(null), 4000);
  }, []);

  const openProfile = useCallback((id: string, el?: Element | null) => {
    origin.current = (el as HTMLElement | null) ?? (document.activeElement as HTMLElement | null);
    setProfileId(id);
  }, []);
  const closeProfile = useCallback(() => setProfileId(null), []);
  const returnFocus = useCallback(() => {
    const el = origin.current;
    if (el && document.contains(el)) el.focus();
  }, []);

  const toggleShortlist = useCallback(
    (c: Customer) => {
      setShortlist((cur) => {
        const has = cur.includes(c.customer_id);
        const next = has ? cur.filter((x) => x !== c.customer_id) : [...cur, c.customer_id];
        writeList("shortlist", next);
        toast(has ? `${customerName(c)} removed from the offer list.` : `${customerName(c)} added to the offer list.`);
        return next;
      });
    },
    [toast],
  );

  const logSent = useCallback((entry: { id: string; offer: string | null }) => {
    writeList("sent-offers", [...readList("sent-offers"), { ...entry, at: new Date().toISOString() }]);
  }, []);

  useEffect(() => {
    // warm the lists the Home page needs while the intro plays
    qc.prefetchQuery({ queryKey: ["home"], queryFn: () => fetch("/home/rows").then((r) => r.json()) });
  }, [qc]);

  const value = useMemo(
    () => ({ profileId, openProfile, closeProfile, toast, toastState, shortlist, toggleShortlist, logSent, segLabel, returnFocus }),
    [profileId, openProfile, closeProfile, toast, toastState, shortlist, toggleShortlist, logSent, segLabel, returnFocus],
  );
  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): Ctx {
  const c = useContext(AppContext);
  if (!c) throw new Error("useApp outside AppProvider");
  return c;
}
