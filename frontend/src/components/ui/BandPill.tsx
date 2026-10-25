import type { ReactNode } from "react";

export type Band = "red" | "amber" | "green";

export interface BandPillProps {
  band: Band;
  children?: ReactNode;
}

const LOOK: Record<Band, string> = {
  red: "border-red text-red bg-red-soft",
  amber: "border-amber text-amber bg-amber-soft",
  green: "border-green text-green bg-green-soft",
};

export function BandPill({ band, children }: BandPillProps) {
  return (
    <span className={`inline-block whitespace-nowrap rounded-pill border px-2 text-[12px] font-semibold leading-[18px] ${LOOK[band]}`}>
      {children ?? band}
    </span>
  );
}
