import { useEffect, useId, useRef, useState } from "react";

export interface InfoTipProps {
  text: string;
  label?: string;
}

/** Small (i) button. Hover or focus opens a popover with the sentence; Escape closes it. */
export function InfoTip({ text, label = "More information" }: InfoTipProps) {
  const id = useId();
  const btn = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState({ left: 8, top: 0 });

  useEffect(() => {
    if (!open || !btn.current) return;
    const r = btn.current.getBoundingClientRect();
    const w = Math.min(280, window.innerWidth - 16);
    setPos({ left: Math.max(8, Math.min(r.left + r.width / 2 - w / 2, window.innerWidth - w - 8)), top: r.bottom + 6 });
  }, [open]);

  return (
    <span className="relative ml-1 inline-flex align-middle">
      <button
        ref={btn}
        type="button"
        aria-label={label}
        aria-describedby={open ? id : undefined}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onClick={() => setOpen((o) => !o)}
        onKeyDown={(e) => {
          if (e.key === "Escape") setOpen(false);
        }}
        className="inline-flex h-4 w-4 items-center justify-center rounded-pill border border-line-200 text-[10px] font-semibold normal-case leading-none tracking-normal text-ink-muted hover:text-ink"
      >
        i
      </button>
      {open && (
        <span
          id={id}
          role="tooltip"
          style={{ position: "fixed", left: pos.left, top: pos.top, maxWidth: Math.min(280, window.innerWidth - 16) }}
          className="z-50 rounded-sm border border-line-100 bg-surface-200 px-3 py-2 text-[13px] font-normal normal-case leading-[18px] tracking-normal text-ink shadow-panel"
        >
          {text}
        </span>
      )}
    </span>
  );
}
