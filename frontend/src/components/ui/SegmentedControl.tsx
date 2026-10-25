export interface SegmentedControlProps {
  options: (string | { value: string; label: string })[];
  value: string;
  onChange?: (v: string) => void;
  label?: string;
}

export function SegmentedControl({ options, value, onChange, label }: SegmentedControlProps) {
  return (
    <div role="radiogroup" aria-label={label} className="flex flex-wrap gap-1">
      {options.map((o) => {
        const opt = typeof o === "string" ? { value: o, label: o } : o;
        const selected = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange?.(opt.value)}
            className={`whitespace-nowrap rounded-sm border px-3 py-1_5 text-[14px] ${
              selected
                ? "border-cyan-soft bg-cyan-soft text-cyan shadow-glow-cyan"
                : "border-line-100 bg-surface-200 text-ink-muted hover:text-ink"
            }`}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
