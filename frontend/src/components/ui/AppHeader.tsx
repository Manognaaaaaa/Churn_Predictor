export interface AppHeaderProps {
  title?: string;
  tabs: string[];
  active: string;
  onTab?: (tab: string) => void;
}

export function AppHeader({ title = "Churn & Revenue Risk", tabs, active, onTab }: AppHeaderProps) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line-100 px-6 py-4">
      <h1 className="t-app-title">{title}</h1>
      <nav className="flex flex-wrap gap-1 rounded-pill border border-line-100 bg-surface-100 p-1">
        {tabs.map((t) => {
          const isActive = t === active;
          return (
            <button
              key={t}
              type="button"
              onClick={() => onTab?.(t)}
              aria-current={isActive ? "page" : undefined}
              className={`rounded-pill px-3 py-1_5 text-[14px] ${
                isActive ? "bg-cyan-soft text-cyan shadow-glow-cyan" : "text-ink-muted hover:text-ink"
              }`}
            >
              {t}
            </button>
          );
        })}
      </nav>
    </header>
  );
}
