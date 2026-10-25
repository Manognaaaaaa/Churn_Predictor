import { useHomeRows } from "../api";
import { Billboard } from "../components/Billboard";
import { CardRow } from "../components/CardRow";
import { Message, Skeleton } from "../components/bits";

export default function Home({ onBudget }: { onBudget: () => void }) {
  const home = useHomeRows();

  if (home.isLoading)
    return (
      <div aria-busy="true" aria-label="Loading customers">
        <div style={{ height: 620, padding: "120px clamp(16px, 3.4vw, 48px)", display: "flex", flexDirection: "column", gap: 18 }}>
          <Skeleton w={220} h={26} r={999} />
          <Skeleton w={420} h={64} />
          <Skeleton w={360} h={18} />
          <Skeleton w={480} h={54} />
        </div>
        <div style={{ display: "flex", gap: 12, padding: "0 clamp(16px, 3.4vw, 48px)" }}>
          {[0, 1, 2, 3, 4].map((k) => <Skeleton key={k} w="100%" h={150} r={10} />)}
        </div>
      </div>
    );
  if (home.error || !home.data) return <Message>The customer lists could not be loaded. Check that the API is running, then reload.</Message>;

  const rows = home.data.rows;
  const top = rows.find((r) => r.key === "top");
  return (
    <>
      {top && top.items.length > 0 ? <Billboard items={top.items} onBudget={onBudget} /> : <Message>No customers to show yet.</Message>}
      <div style={{ position: "relative", marginTop: -84, display: "flex", flexDirection: "column", gap: 6, paddingBottom: 64 }}>
        {rows.length === 0 && <Message>No customer lists are available.</Message>}
        {rows.map((r, ri) => (
          <CardRow key={r.key} title={r.title} count={r.count} items={r.items} ranked={r.key === "top"} delay={ri * 120} />
        ))}
      </div>
    </>
  );
}
