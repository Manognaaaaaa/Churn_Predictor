import { createContext, useContext } from "react";

export interface CustomerFilter {
  band?: "red" | "amber" | "green";
  segment?: string;
}
export interface LastAllocation {
  budget: number;
  spent: number;
  expected_revenue_saved: number;
}

interface Session {
  openCustomers: (f: CustomerFilter) => void;
  initialFilter: CustomerFilter | null;
  lastAllocation: LastAllocation | null;
  setLastAllocation: (a: LastAllocation) => void;
}

/** State shared across pages: cross-page navigation with a filter, and the latest allocation run. */
export const SessionContext = createContext<Session>({
  openCustomers: () => {},
  initialFilter: null,
  lastAllocation: null,
  setLastAllocation: () => {},
});
export const useSession = () => useContext(SessionContext);
