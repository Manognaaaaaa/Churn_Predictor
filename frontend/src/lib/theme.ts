export function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name.startsWith("--") ? name : `--${name}`).trim();
}

export function chartColors() {
  return {
    actual: cssVar("--chart-actual"),
    forecast: cssVar("--chart-forecast"),
    interval: cssVar("--chart-interval"),
    grid: cssVar("--chart-grid"),
    axis: cssVar("--chart-axis"),
    ink: cssVar("--ink"),
    inkMuted: cssVar("--ink-muted"),
    surface100: cssVar("--surface-100"),
    surface200: cssVar("--surface-200"),
    line100: cssVar("--line-100"),
    red: cssVar("--red"),
    amber: cssVar("--amber"),
    green: cssVar("--green"),
    purple: cssVar("--purple"),
  };
}

export function tooltipStyle() {
  const c = chartColors();
  return {
    contentStyle: {
      background: c.surface200,
      border: `1px solid ${c.line100}`,
      borderRadius: 6,
      color: c.ink,
    },
    labelStyle: { color: c.ink },
    itemStyle: { color: c.ink },
  };
}
