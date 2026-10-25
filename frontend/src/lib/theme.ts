export function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name.startsWith("--") ? name : `--${name}`).trim();
}
