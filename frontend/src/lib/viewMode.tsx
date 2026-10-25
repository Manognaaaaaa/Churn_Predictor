import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";

export type ViewMode = "manager" | "analyst";
const KEY = "churn-view-mode";

function read(): ViewMode {
  try {
    return localStorage.getItem(KEY) === "analyst" ? "analyst" : "manager";
  } catch {
    return "manager";
  }
}

interface Ctx {
  mode: ViewMode;
  isManager: boolean;
  setMode: (m: ViewMode) => void;
}
const ViewModeContext = createContext<Ctx>({ mode: "manager", isManager: true, setMode: () => {} });

export function ViewModeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<ViewMode>(read);
  const setMode = useCallback((m: ViewMode) => {
    setModeState(m);
    try {
      localStorage.setItem(KEY, m);
    } catch {
      /* storage blocked: the choice lasts for this visit only */
    }
  }, []);
  const value = useMemo(() => ({ mode, isManager: mode === "manager", setMode }), [mode, setMode]);
  return <ViewModeContext.Provider value={value}>{children}</ViewModeContext.Provider>;
}

export const useViewMode = () => useContext(ViewModeContext);
