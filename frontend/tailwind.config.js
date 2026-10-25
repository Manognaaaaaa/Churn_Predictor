/** @type {import('tailwindcss').Config} */
const v = (name) => `var(--${name})`;

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    // Replaces Tailwind's default palette: only token colors exist.
    colors: {
      transparent: "transparent",
      current: "currentColor",
      bg: { "000": v("bg-000"), "100": v("bg-100"), glow: v("bg-glow") },
      surface: { "100": v("surface-100"), "200": v("surface-200"), "300": v("surface-300") },
      line: { "100": v("line-100"), "200": v("line-200") },
      ink: { DEFAULT: v("ink"), muted: v("ink-muted"), faint: v("ink-faint"), inverse: v("ink-inverse") },
      cyan: { DEFAULT: v("cyan"), strong: v("cyan-strong"), soft: v("cyan-soft") },
      gold: { DEFAULT: v("gold"), soft: v("gold-soft") },
      red: { DEFAULT: v("red"), soft: v("red-soft") },
      amber: { DEFAULT: v("amber"), soft: v("amber-soft") },
      green: { DEFAULT: v("green"), soft: v("green-soft") },
      purple: { DEFAULT: v("purple"), soft: v("purple-soft") },
      field: v("field"),
    },
    extend: {
      fontFamily: {
        sans: v("font-sans"),
        display: v("font-display"),
        mono: v("font-mono"),
      },
      borderRadius: {
        sm: v("radius-sm"),
        md: v("radius-md"),
        lg: v("radius-lg"),
        pill: v("radius-pill"),
      },
      boxShadow: {
        panel: v("shadow-panel"),
        "glow-gold": v("glow-gold"),
        "glow-cyan": v("glow-cyan"),
        "glow-red": v("glow-red"),
        focus: v("focus-ring"),
      },
      spacing: {
        "1_5": v("space-1_5"),
      },
    },
  },
  plugins: [],
};
