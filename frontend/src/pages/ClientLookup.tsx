import { useState } from "react";
import { useCustomer, useCustomers, usePortfolio } from "../api";
import type { CustomerRow } from "../api";
import { fmtMoney, fmtPct } from "../lib/format";
import {
  CUSTOMER_CURRENCY, GLOSSARY, chanceText, driverLabel, moneyFull, offerLabel, riskWord,
} from "../lib/plain";
import { useSegmentLabel } from "../lib/usePlain";
import { useViewMode } from "../lib/viewMode";
import { useSession } from "../lib/session";
import {
  BandPill, Button, DataTable, DriverList, Headline, InfoTip, Key, Panel, RecommendationCard, SegmentedControl, TextInput,
} from "../components/ui";
import type { Band } from "../components/ui";
import type { Column } from "../components/ui/DataTable";

const BAND_VALUES = ["all", "red", "amber", "green"];
const BAND_PHRASE: Record<string, string> = { red: "high-risk ", amber: "medium-risk ", green: "low-risk " };
const SHOWN_LIMIT = 500;

export default function ClientLookup() {
  const { isManager } = useViewMode();
  const { initialFilter } = useSession();
  const segLabel = useSegmentLabel();
  const portfolio = usePortfolio();
  const [band, setBand] = useState<string>(initialFilter?.band ?? "");
  const [segment, setSegment] = useState<string>(initialFilter?.segment ?? "");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);
  const customers = useCustomers(band, SHOWN_LIMIT);
  const detail = useCustomer(selected);

  const items = (customers.data?.items ?? []).filter(
    (c) =>
      (!search || c.customer_id.toLowerCase().includes(search.toLowerCase())) &&
      (!segment || c.segment_name === segment),
  );
  const d = detail.data;
  const total = customers.data?.total ?? 0;

  const columns: Column<CustomerRow>[] = isManager
    ? [
        { key: "customer_id", label: "Customer", mono: true },
        { key: "p_churn_calibrated", label: <>Chance of leaving<InfoTip text={GLOSSARY.chance} /></>, align: "right", render: (r) => chanceText(r.p_churn_calibrated) },
        { key: "risk_band", label: <>Risk<InfoTip text={GLOSSARY.band} /></>, render: (r) => <BandPill band={r.risk_band}>{riskWord(r.risk_band)}</BandPill> },
        { key: "revenue_at_risk", label: `Revenue at risk (${CUSTOMER_CURRENCY})`, align: "right", render: (r) => fmtMoney(r.revenue_at_risk) },
        { key: "segment_name", label: <>Group<InfoTip text={GLOSSARY.group} /></>, muted: true, render: (r) => segLabel(r.segment_name) },
      ]
    : [
        { key: "customer_id", label: "Customer", mono: true },
        { key: "p_churn_calibrated", label: "P(churn)", align: "right", render: (r) => fmtPct(r.p_churn_calibrated) },
        { key: "risk_band", label: "Band", render: (r) => <BandPill band={r.risk_band} /> },
        { key: "revenue_at_risk", label: "Revenue at risk", align: "right", render: (r) => fmtMoney(r.revenue_at_risk) },
        { key: "segment_name", label: "Segment", muted: true, render: (r) => r.segment_name ?? "–" },
      ];

  const bandOptions = isManager
    ? [
        { value: "all", label: "All" },
        { value: "red", label: "High risk" },
        { value: "amber", label: "Medium risk" },
        { value: "green", label: "Low risk" },
      ]
    : BAND_VALUES;

  const groupLine = d?.segment ? `${segLabel(d.segment.segment_name)}, ${d.segment.value_tier} value` : null;
  const drivers = (d?.top_drivers ?? []).map((x) => ({
    ...x,
    label: isManager ? driverLabel(x.feature, x.label) : x.label,
  }));

  return (
    <>
      <Headline>
        {segment ? (
          <>
            Showing <Key>{fmtMoney(items.length)} {BAND_PHRASE[band] ?? ""}customers</Key>{" "}
            {segLabel(segment).replace(/^Customers /, "")} among the {SHOWN_LIMIT} with the most revenue at risk. Click a customer to see
            why they might leave and what to offer.
          </>
        ) : (
          <>
            Showing <Key>{fmtMoney(search ? items.length : total)} {BAND_PHRASE[band] ?? ""}customers</Key>, sorted by revenue at risk.
            Click a customer to see why they might leave and what to offer.
          </>
        )}
      </Headline>
      <div className="grid-lookup">
        <div className="flex min-w-0 flex-col gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <div className="min-w-[200px] flex-1">
              <TextInput
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={isManager ? "Search customer ID" : "Search customer id"}
                aria-label="Search customer ID"
              />
            </div>
            <SegmentedControl
              label={isManager ? "Risk" : "Risk band"}
              options={bandOptions}
              value={band || "all"}
              onChange={(v) => setBand(v === "all" ? "" : v)}
            />
          </div>
          <label className="flex flex-wrap items-center gap-2">
            <span className="t-label">{isManager ? "Customer group" : "Segment"}</span>
            <select
              value={segment}
              onChange={(e) => setSegment(e.target.value)}
              className="min-w-0 max-w-full rounded-sm border border-line-200 bg-surface-200 px-3 py-1_5 text-[14px] text-ink"
            >
              <option value="">{isManager ? "All groups" : "All segments"}</option>
              {(portfolio.data?.by_segment ?? []).map((s) => (
                <option key={s.segment_name} value={s.segment_name}>
                  {isManager ? segLabel(s.segment_name) : s.segment_name}
                </option>
              ))}
            </select>
          </label>
          <DataTable
            columns={columns}
            rows={items}
            rowKey="customer_id"
            onRowClick={(r) => setSelected(r.customer_id)}
            selectedKey={selected ?? undefined}
            footer={
              customers.data &&
              (isManager
                ? `${fmtMoney(items.length)} of ${fmtMoney(total)} customers shown (the ${SHOWN_LIMIT} with the most revenue at risk)`
                : `${fmtMoney(items.length)} of ${fmtMoney(total)} shown (top 500 by revenue at risk)`)
            }
          />
        </div>

        <div className="min-w-0">
          {!selected && (
            <p className="msg">
              {isManager
                ? "Select a customer to see why they might leave and what to offer them."
                : "Select a customer to see their risk profile."}
            </p>
          )}
          {selected && detail.isLoading && <p className="msg">Loading…</p>}
          {selected && d && !isManager && (
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
                <DriverList title="Top churn drivers (SHAP)" drivers={drivers} />
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
          {selected && d && isManager && (
            <Panel eyebrow="Customer" title={`Customer ${d.customer_id}`}>
              <div className="grid gap-4">
                <div className="grid gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <BandPill band={d.risk_band}>{riskWord(d.risk_band as Band)}</BandPill>
                    {groupLine && <span className="t-caption">{groupLine}</span>}
                  </div>
                  <p className="m-0 text-[14px] leading-5">
                    {riskWord(d.risk_band as Band)}: {chanceText(d.p_churn_calibrated)} chance of leaving.{" "}
                    {moneyFull(d.revenue_at_risk)} of revenue at risk.
                  </p>
                </div>

                <div className="grid gap-2">
                  <h3 className="t-label m-0">Why the model thinks this</h3>
                  <DriverList plain drivers={showAll ? drivers : drivers.slice(0, 3)} />
                  {drivers.length > 3 && (
                    <div>
                      <Button variant="ghost" className="!px-0" onClick={() => setShowAll((s) => !s)}>
                        {showAll ? "Show fewer reasons" : "Show all reasons"}
                      </Button>
                    </div>
                  )}
                </div>

                {d.allocation && (
                  <div className="grid gap-2">
                    <h3 className="t-label m-0">What to do</h3>
                    <RecommendationCard
                      plain
                      eyebrow="Suggested offer"
                      currency={CUSTOMER_CURRENCY}
                      offer={offerLabel(d.allocation.offer)}
                      spend={d.allocation.spend}
                      saved={d.allocation.expected_revenue_saved}
                    />
                  </div>
                )}

                <div>
                  <Button
                    variant="primary"
                    onClick={() => window.open(`/customers/${d.customer_id}/report.pdf`, "_blank", "noopener,noreferrer")}
                  >
                    Download customer report
                  </Button>
                </div>
              </div>
            </Panel>
          )}
        </div>
      </div>
    </>
  );
}
