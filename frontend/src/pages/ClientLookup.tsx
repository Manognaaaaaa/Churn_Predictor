import { useState } from "react";
import { useCustomer, useCustomers } from "../api";
import type { CustomerRow } from "../api";
import { fmtMoney, fmtPct } from "../lib/format";
import {
  BandPill, Button, DataTable, DriverList, Panel, RecommendationCard, SegmentedControl, TextInput,
} from "../components/ui";
import type { Column } from "../components/ui/DataTable";

const BANDS = ["all", "red", "amber", "green"];

const COLUMNS: Column<CustomerRow>[] = [
  { key: "customer_id", label: "Customer", mono: true },
  { key: "p_churn_calibrated", label: "P(churn)", align: "right", render: (r) => fmtPct(r.p_churn_calibrated) },
  { key: "risk_band", label: "Band", render: (r) => <BandPill band={r.risk_band} /> },
  { key: "revenue_at_risk", label: "Revenue at risk", align: "right", render: (r) => fmtMoney(r.revenue_at_risk) },
  { key: "segment_name", label: "Segment", muted: true, render: (r) => r.segment_name ?? "–" },
];

export default function ClientLookup() {
  const [band, setBand] = useState<string>("");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const customers = useCustomers(band, 500);
  const detail = useCustomer(selected);

  const items = (customers.data?.items ?? []).filter(
    (c) => !search || c.customer_id.toLowerCase().includes(search.toLowerCase()),
  );
  const d = detail.data;

  return (
    <div className="grid-lookup">
      <div className="flex min-w-0 flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <div className="min-w-[200px] flex-1">
            <TextInput
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search customer id"
              aria-label="Search customer id"
            />
          </div>
          <SegmentedControl label="Risk band" options={BANDS} value={band || "all"} onChange={(v) => setBand(v === "all" ? "" : v)} />
        </div>
        <DataTable
          columns={COLUMNS}
          rows={items}
          rowKey="customer_id"
          onRowClick={(r) => setSelected(r.customer_id)}
          selectedKey={selected ?? undefined}
          footer={customers.data && `${fmtMoney(items.length)} of ${fmtMoney(customers.data.total)} shown (top 500 by revenue at risk)`}
        />
      </div>

      <div className="min-w-0">
        {!selected && <p className="msg">Select a customer to see their risk profile.</p>}
        {selected && detail.isLoading && <p className="msg">Loading…</p>}
        {selected && d && (
          <Panel eyebrow="Customer" title="Risk profile">
            <div className="grid gap-4">
              <div className="grid gap-1">
                <div className="t-id">{d.customer_id}</div>
                <div className="flex flex-wrap items-center gap-3">
                  <BandPill band={d.risk_band} />
                  <span className="t-hero">{fmtPct(d.p_churn_calibrated)}</span>
                  <span className="t-caption">churn · raw {fmtPct(d.p_churn_raw)}</span>
                </div>
                <div>
                  Revenue at risk: <span className="t-metric">{fmtMoney(d.revenue_at_risk)}</span>
                </div>
                {d.segment && (
                  <div className="t-caption">
                    Segment: {d.segment.segment_name} · {d.segment.value_tier} value
                  </div>
                )}
              </div>

              <DriverList title="Top churn drivers (SHAP)" drivers={d.top_drivers} />

              {d.allocation && (
                <RecommendationCard
                  offer={d.allocation.offer}
                  spend={d.allocation.spend}
                  saved={d.allocation.expected_revenue_saved}
                  reason={d.allocation.reason}
                />
              )}

              <div>
                <Button
                  variant="primary"
                  onClick={() => window.open(`/customers/${d.customer_id}/report.pdf`, "_blank", "noopener,noreferrer")}
                >
                  Download PDF report
                </Button>
              </div>
            </div>
          </Panel>
        )}
      </div>
    </div>
  );
}
