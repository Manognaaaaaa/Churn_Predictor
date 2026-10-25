import { useReducedMotion } from "../hooks/useReducedMotion";

/** Rolling number: every digit is a 0 to 9 column that slides, 60ms apart per digit. */
export function Odometer({ value, pad = 8, height = 92, size = 84 }: { value: number; pad?: number; height?: number; size?: number }) {
  const reduced = useReducedMotion();
  const s = String(Math.max(0, Math.round(value))).padStart(pad, "0");
  const lead = s.length - String(Math.max(0, Math.round(value))).length;
  const cols: JSX.Element[] = [];
  for (let i = 0; i < s.length; i++) {
    const hidden = i < lead;
    if (i > 0 && (s.length - i) % 3 === 0) cols.push(<span key={`c${i}`} style={{ display: hidden ? "none" : undefined }}>,</span>);
    cols.push(
      <span key={`d${s.length - i}`} style={{ display: hidden ? "none" : "inline-block", height, overflow: "hidden" }}>
        <span className="digit-col" style={{ transform: `translateY(-${Number(s[i]) * 10}%)`, transitionDelay: reduced ? "0ms" : `${i * 60}ms` }}>
          {"0123456789".split("").map((d) => <span key={d} style={{ height }}>{d}</span>)}
        </span>
      </span>,
    );
  }
  return (
    <div role="text" aria-live="polite" aria-label={`Plus ${Math.round(value).toLocaleString("en-US")}`} style={{ display: "flex", fontWeight: 300, fontSize: size, lineHeight: `${height}px`, letterSpacing: "-0.05em", position: "relative" }}>
      <span style={{ color: "var(--blue-200)" }} aria-hidden="true">+</span>
      <span aria-hidden="true" style={{ display: "flex" }}>{cols}</span>
    </div>
  );
}
