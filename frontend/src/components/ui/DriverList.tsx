export interface DriverListProps {
  drivers: { label: string; contribution: number }[];
  title?: string;
  scale?: number;
}

export function DriverList({ drivers, title, scale = 2 }: DriverListProps) {
  return (
    <div className="grid gap-2">
      {title && <div className="t-label">{title}</div>}
      {drivers.map((d) => {
        const c = d.contribution;
        const w = Math.min(50, (Math.abs(c) / scale) * 50);
        const positive = c > 0;
        return (
          <div key={d.label}>
            <div className="flex items-baseline justify-between gap-3 text-[12px] leading-4">
              <span>{d.label}</span>
              <span className="font-mono">
                {positive ? "+" : ""}
                {c.toFixed(2)}
              </span>
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
