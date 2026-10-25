import type { ReactNode } from "react";

export interface Column<R> {
  key: string;
  label: string;
  align?: "left" | "right";
  mono?: boolean;
  muted?: boolean;
  tone?: "green" | "red" | "amber" | "gold";
  render?: (r: R) => ReactNode;
}

export interface DataTableProps<R> {
  columns: Column<R>[];
  rows: R[];
  rowKey: string;
  onRowClick?: (r: R) => void;
  selectedKey?: string;
  highlightKey?: string;
  footer?: ReactNode;
}

const TONE: Record<string, string> = { green: "text-green", red: "text-red", amber: "text-amber", gold: "text-gold" };

export function DataTable<R extends object>({
  columns, rows, rowKey, onRowClick, selectedKey, highlightKey, footer,
}: DataTableProps<R>) {
  const keyOf = (r: R) => String((r as Record<string, unknown>)[rowKey]);
  return (
    <div className="overflow-hidden rounded-lg border border-line-100 bg-surface-100 shadow-panel">
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[14px]">
          <thead>
            <tr>
              {columns.map((c) => (
                <th
                  key={c.key}
                  className={`t-label border-b border-line-100 bg-surface-200 px-3 py-2 ${
                    c.align === "right" ? "text-right" : "text-left"
                  }`}
                >
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const k = keyOf(r);
              const selected = selectedKey !== undefined && k === selectedKey;
              const best = highlightKey !== undefined && k === highlightKey;
              const last = i === rows.length - 1;
              return (
                <tr
                  key={k}
                  onClick={onRowClick ? () => onRowClick(r) : undefined}
                  onKeyDown={
                    onRowClick
                      ? (e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            onRowClick(r);
                          }
                        }
                      : undefined
                  }
                  tabIndex={onRowClick ? 0 : undefined}
                  aria-selected={onRowClick ? selected : undefined}
                  className={`${onRowClick ? "cursor-pointer hover:bg-surface-300" : ""} ${
                    selected ? "bg-surface-300" : ""
                  } ${best ? "font-semibold text-gold" : ""}`}
                >
                  {columns.map((c) => {
                    const raw = (r as Record<string, unknown>)[c.key];
                    const color = best
                      ? "text-gold"
                      : c.tone
                        ? TONE[c.tone]
                        : c.muted
                          ? "text-ink-muted"
                          : "text-ink";
                    return (
                      <td
                        key={c.key}
                        className={`px-3 py-1_5 tabular-nums ${last ? "" : "border-b border-line-100"} ${color} ${
                          c.align === "right" ? "text-right" : "text-left"
                        } ${c.mono ? "t-id" : ""}`}
                      >
                        {c.render ? c.render(r) : String(raw ?? "–")}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {footer && <div className="border-t border-line-100 px-3 py-2 text-[12px] text-ink-faint">{footer}</div>}
    </div>
  );
}
