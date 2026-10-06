import { useState } from "react";
import Overview from "./pages/Overview";
import ClientLookup from "./pages/ClientLookup";
import BudgetPlanner from "./pages/BudgetPlanner";
import ModelData from "./pages/ModelData";

const TABS = ["Overview", "Client Lookup", "Budget Planner", "Model & Data"] as const;
type Tab = (typeof TABS)[number];

export default function App() {
  const [tab, setTab] = useState<Tab>("Overview");
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-6 py-4 flex items-center justify-between">
        <h1 className="text-xl font-semibold">Churn &amp; Revenue Risk</h1>
        <nav className="flex gap-1">
          {TABS.map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-3 py-1.5 rounded-md text-sm transition ${
                tab === t ? "bg-slate-700 text-white" : "text-slate-400 hover:text-white"
              }`}
            >
              {t}
            </button>
          ))}
        </nav>
      </header>
      <main className="p-6 max-w-6xl mx-auto">
        {tab === "Overview" && <Overview />}
        {tab === "Client Lookup" && <ClientLookup />}
        {tab === "Budget Planner" && <BudgetPlanner />}
        {tab === "Model & Data" && <ModelData />}
      </main>
    </div>
  );
}
