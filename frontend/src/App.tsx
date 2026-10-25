import { useState } from "react";
import Overview from "./pages/Overview";
import ClientLookup from "./pages/ClientLookup";
import BudgetPlanner from "./pages/BudgetPlanner";
import ModelData from "./pages/ModelData";
import UiPreview from "./pages/UiPreview";
import { AppHeader } from "./components/ui";

const TABS = ["Overview", "Client Lookup", "Budget Planner", "Model & Data"] as const;
type Tab = (typeof TABS)[number];

const SHOW_PREVIEW = import.meta.env.DEV && new URLSearchParams(window.location.search).has("preview");

export default function App() {
  const [tab, setTab] = useState<Tab>("Overview");
  if (SHOW_PREVIEW) return <UiPreview />;
  return (
    <div className="min-h-screen">
      <AppHeader title="Churn & Revenue Risk" tabs={[...TABS]} active={tab} onTab={(t) => setTab(t as Tab)} />
      <main className="page">
        {tab === "Overview" && <Overview />}
        {tab === "Client Lookup" && <ClientLookup />}
        {tab === "Budget Planner" && <BudgetPlanner />}
        {tab === "Model & Data" && <ModelData />}
      </main>
    </div>
  );
}
