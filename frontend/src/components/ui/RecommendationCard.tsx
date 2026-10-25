import { fmtMoney } from "../../lib/format";

export interface RecommendationCardProps {
  offer: string;
  spend: number;
  saved: number;
  reason?: string;
  eyebrow?: string;
}

export function RecommendationCard({ offer, spend, saved, reason, eyebrow = "Recommended" }: RecommendationCardProps) {
  return (
    <div className="grid gap-1 rounded-md border border-cyan-soft bg-cyan-soft p-3 shadow-glow-cyan">
      <div className="t-eyebrow">{eyebrow}</div>
      <div className="font-mono text-[15px] font-semibold leading-[22px] text-ink">{offer}</div>
      <div className="text-[13px] text-ink-muted">
        Spend <b className="font-bold text-ink">{fmtMoney(spend)}</b> → save{" "}
        <b className="font-bold text-green">{fmtMoney(saved)}</b>
      </div>
      {reason && <div className="t-caption">{reason}</div>}
    </div>
  );
}
