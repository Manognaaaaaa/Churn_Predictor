import { fmtMoney } from "../../lib/format";

export interface RecommendationCardProps {
  offer: string;
  spend: number;
  saved: number;
  reason?: string;
  eyebrow?: string;
  /** Manager wording: readable offer name and a full sentence instead of the arrow summary. */
  plain?: boolean;
  currency?: string;
}

export function RecommendationCard({ offer, spend, saved, reason, eyebrow = "Recommended", plain, currency = "" }: RecommendationCardProps) {
  return (
    <div className="grid gap-1 rounded-md border border-cyan-soft bg-cyan-soft p-3 shadow-glow-cyan">
      <div className="t-eyebrow">{eyebrow}</div>
      <div className={`text-[15px] font-semibold leading-[22px] text-ink ${plain ? "" : "font-mono"}`}>{offer}</div>
      {plain ? (
        <div className="text-[13px] text-ink-muted">
          Spend <b className="font-bold text-ink">{currency}{fmtMoney(spend)}</b> to keep an expected{" "}
          <b className="font-bold text-green">{currency}{fmtMoney(saved)}</b> of revenue.
        </div>
      ) : (
        <div className="text-[13px] text-ink-muted">
          Spend <b className="font-bold text-ink">{fmtMoney(spend)}</b> → save{" "}
          <b className="font-bold text-green">{fmtMoney(saved)}</b>
        </div>
      )}
      {reason && !plain && <div className="t-caption">{reason}</div>}
    </div>
  );
}
