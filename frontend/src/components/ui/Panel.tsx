import type { ReactNode } from "react";

export interface PanelProps {
  title?: string;
  eyebrow?: string;
  actions?: ReactNode;
  note?: string;
  flush?: boolean;
  className?: string;
  children?: ReactNode;
}

export function Panel({ title, eyebrow, actions, note, flush, className = "", children }: PanelProps) {
  const hasHead = title || eyebrow || actions;
  return (
    <section
      className={`min-w-0 rounded-lg border border-line-100 bg-surface-100 shadow-panel ${
        flush ? "overflow-hidden" : "p-4"
      } ${className}`}
    >
      {hasHead && (
        <div className={`mb-3 flex items-start justify-between gap-3 ${flush ? "p-4 pb-0" : ""}`}>
          <div>
            {eyebrow && <div className="t-eyebrow">{eyebrow}</div>}
            {title && <h2 className="t-panel-title">{title}</h2>}
          </div>
          {actions && <div className="flex flex-wrap items-center justify-end gap-2">{actions}</div>}
        </div>
      )}
      {children}
      {note && <p className={`t-caption mt-2 ${flush ? "px-4 pb-4" : ""}`}>{note}</p>}
    </section>
  );
}
