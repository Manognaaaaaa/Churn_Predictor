export interface DriverListProps {
  drivers: { label: string; contribution: number }[];
  title?: string;
  scale?: number;
  /** Manager wording: no raw numbers, a words-based legend and "raises"/"lowers" next to each bar. */
  plain?: boolean;
}

export function DriverList({ drivers, title, scale = 2, plain }: DriverListProps) {
  return (
    <div className="grid gap-2">
      {title && <div className="t-label">{title}</div>}
      {plain && (
        <div className="flex gap-4 text-[12px] text-ink-muted">
          <span><span className="mr-1 inline-block h-2 w-2 rounded-pill bg-red" />raises risk</span>
          <span><span className="mr-1 inline-block h-2 w-2 rounded-pill bg-green" />lowers risk</span>
        </div>
      )}
      {drivers.map((d) => {
        const c = d.contribution;
        const w = Math.min(50, (Math.abs(c) / scale) * 50);
        const positive = c > 0;
        return (
          <div key={d.label}>
            <div className="flex items-baseline justify-between gap-3 text-[12px] leading-4">
              <span>{d.label}</span>
              {plain ? (
                <span className={positive ? "text-red" : "text-green"}>{positive ? "raises risk" : "lowers risk"}</span>
              ) : (
                <span className="font-mono">
                  {positive ? "+" : ""}
                  {c.toFixed(2)}
                </span>
              )}
            </div>
            <div className="relative mt-[2px] h-[6px] rounded-pill bg-surface-300">
              <div
                className={`absolute top-0 h-[6px] rounded-pill ${positive ? "bg-red" : "bg-green"}`}
                style={{ width: `${w}%`, left: positive ? "50%" : `${50 - w}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
