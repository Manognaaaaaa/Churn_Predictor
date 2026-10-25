import type { ReactNode } from "react";

/** Key figure inside a headline sentence. */
export function Key({ children }: { children: ReactNode }) {
  return <b className="font-semibold text-cyan">{children}</b>;
}

/** One-sentence answer to the question a manager asks on this screen. */
export function Headline({ children }: { children: ReactNode }) {
  return <p className="m-0 text-[20px] font-medium leading-[28px] text-ink">{children}</p>;
}
