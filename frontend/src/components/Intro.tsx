import { useEffect } from "react";

/** Brand intro: bloom, a ring that draws itself, the name tightening in, a rule, a tagline. Lifts away at 2.9s. */
export function Intro({ onDone }: { onDone: () => void }) {
  useEffect(() => {
    const t = window.setTimeout(onDone, 2900);
    return () => window.clearTimeout(t);
  }, [onDone]);
  return (
    <div className="intro" aria-hidden="true">
      <div className="bloom" />
      <svg className="mark" viewBox="0 0 64 64">
        <circle cx="32" cy="32" r="27" fill="none" stroke="rgba(var(--blue-200-rgb), .18)" strokeWidth={3} />
        <circle className="markArc" cx="32" cy="32" r="27" fill="none" stroke="var(--blue-200)" transform="rotate(-90 32 32)" strokeWidth={3} strokeLinecap="round" />
        <circle cx="32" cy="32" r="6" fill="var(--ink)" />
      </svg>
      <div className="word">Churn &amp; Revenue Risk</div>
      <div className="rule" />
      <div className="introSub">RETENTION INTELLIGENCE</div>
    </div>
  );
}

const KEY = "intro-seen";
export function introAlreadySeen(): boolean {
  try {
    return sessionStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}
export function markIntroSeen() {
  try {
    sessionStorage.setItem(KEY, "1");
  } catch {
    /* storage blocked: the intro may play again on reload */
  }
}
