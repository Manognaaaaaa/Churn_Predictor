import { useCallback, useMemo, useState } from "react";
import Overview from "./pages/Overview";
import ClientLookup from "./pages/ClientLookup";
import BudgetPlanner from "./pages/BudgetPlanner";
import ModelData from "./pages/ModelData";
import UiPreview from "./pages/UiPreview";
import { AppHeader, SegmentedControl } from "./components/ui";
import { ViewModeProvider, useViewMode } from "./lib/viewMode";
import type { ViewMode } from "./lib/viewMode";
import { SessionContext } from "./lib/session";
import type { CustomerFilter, LastAllocation } from "./lib/session";

const TABS = [
  { value: "overview", analyst: "Overview", manager: "Summary" },
  { value: "lookup", analyst: "Client Lookup", manager: "Customers" },
  { value: "budget", analyst: "Budget Planner", manager: "Retention budget" },
  { value: "model", analyst: "Model & Data", manager: "Can we trust this?" },
] as const;
type Tab = (typeof TABS)[number]["value"];

const VIEWS = [
  { value: "manager", label: "Manager view" },
  { value: "analyst", label: "Analyst view" },
];

const SHOW_PREVIEW = import.meta.env.DEV && new URLSearchParams(window.location.search).has("preview");

function Shell() {
  const { mode, setMode } = useViewMode();
  const [tab, setTab] = useState<Tab>("overview");
  const [filter, setFilter] = useState<CustomerFilter | null>(null);
  const [lastAllocation, setLastAllocation] = useState<LastAllocation | null>(null);

  const openCustomers = useCallback((f: CustomerFilter) => {
    setFilter(f);
    setTab("lookup");
  }, []);
  const session = useMemo(
    () => ({ openCustomers, initialFilter: filter, lastAllocation, setLastAllocation }),
    [openCustomers, filter, lastAllocation],
  );

  return (
    <SessionContext.Provider value={session}>
      <div className="min-h-screen">
        <AppHeader
          title="Churn & Revenue Risk"
          tabs={TABS.map((t) => ({ value: t.value, label: t[mode] }))}
          active={tab}
          onTab={(t) => {
            setFilter(null);
            setTab(t as Tab);
          }}
          actions={<SegmentedControl label="View mode" options={VIEWS} value={mode} onChange={(v) => setMode(v as ViewMode)} />}
        />
        <main className="page">
          {tab === "overview" && <Overview />}
          {tab === "lookup" && <ClientLookup />}
          {tab === "budget" && <BudgetPlanner />}
          {tab === "model" && <ModelData />}
        </main>
      </div>
    </SessionContext.Provider>
  );
}

export default function App() {
  if (SHOW_PREVIEW) return <UiPreview />;
  return (
    <ViewModeProvider>
      <Shell />
    </ViewModeProvider>
  );
}
