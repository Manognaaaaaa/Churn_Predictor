import { useState } from "react";
import {
  AppHeader, BandPill, Button, DataTable, DriverList, KpiCard, Panel, RecommendationCard, SegmentedControl, TextInput,
} from "../components/ui";

const rows = [
  { id: "C-001", p: "67.6%", band: "red" as const },
  { id: "C-002", p: "31.0%", band: "amber" as const },
  { id: "C-003", p: "4.2%", band: "green" as const },
];

/** Dev-only component gallery: open with `?preview`. */
export default function UiPreview() {
  const [tab, setTab] = useState("Overview");
  const [seg, setSeg] = useState("b");
  return (
    <div>
      <AppHeader tabs={["Overview", "Client Lookup", "Budget Planner", "Model & Data"]} active={tab} onTab={setTab} />
      <main className="page">
        <div className="grid-kpi">
          <KpiCard label="Default" value={208100843} />
          <KpiCard label="Unit and delta" value={12} unit="pts" delta="+3.1%" deltaTone="up" />
          <KpiCard label="Highlight" value="0.1018" tone="highlight" delta="-0.2" deltaTone="down" />
          <KpiCard label="Positive" value={1234567} tone="positive" />
        </div>
        <Panel eyebrow="Eyebrow" title="Controls" actions={<Button variant="ghost">Ghost</Button>} note="Caption note">
          <div className="flex flex-wrap items-center gap-3">
            <SegmentedControl label="demo" options={["a", "b", "c"]} value={seg} onChange={setSeg} />
            <Button variant="primary">Primary</Button>
            <Button>Secondary</Button>
            <Button variant="primary" disabled>Optimising…</Button>
            <TextInput placeholder="Field" />
            <TextInput variant="prompt" placeholder="Prompt" />
            <BandPill band="red" /> <BandPill band="amber" /> <BandPill band="green" />
          </div>
        </Panel>
        <div className="grid-2">
          <DataTable
            columns={[
              { key: "id", label: "Customer", mono: true },
              { key: "p", label: "P(churn)", align: "right", tone: "gold" },
              { key: "band", label: "Band", render: (r) => <BandPill band={r.band} /> },
            ]}
            rows={rows}
            rowKey="id"
            onRowClick={() => undefined}
            selectedKey="C-002"
            highlightKey="C-003"
            footer="3 of 3 shown"
          />
          <Panel title="Drivers">
            <div className="grid gap-4">
              <DriverList title="Top drivers" drivers={[{ label: "Tenure", contribution: 1.2 }, { label: "Contract", contribution: -0.8 }]} />
              <RecommendationCard offer="fee_waiver" spend={1200} saved={5400} reason="High value, price sensitive." />
            </div>
          </Panel>
        </div>
      </main>
    </div>
  );
}
