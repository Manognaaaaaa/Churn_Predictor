/** @type {import('tailwindcss').Config} */
const v = (name) => `var(--${name})`;

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    // Only token colours exist; no raw hex in components.
    colors: {
      transparent: "transparent",
      current: "currentColor",
      bg: { DEFAULT: v("bg"), raised: v("bg-raised"), intro: v("bg-intro") },
      line: { DEFAULT: v("line"), strong: v("line-strong"), grid: v("grid-line") },
      ink: { DEFAULT: v("ink"), soft: v("ink-soft"), muted: v("ink-muted"), faint: v("ink-faint"), inverse: v("ink-inverse"), chip: v("ink-chip") },
      blue: { 100: v("blue-100"), 200: v("blue-200"), 300: v("blue-300"), 400: v("blue-400"), 500: v("blue-500"), 700: v("blue-700"), 900: v("blue-900") },
      white: v("white"),
    },
    extend: {
      fontFamily: { sans: v("font") },
      boxShadow: { focus: v("focus") },
      transitionTimingFunction: { out: v("ease"), "in-out": v("ease-io"), spring: v("spring") },
    },
  },
  plugins: [],
};
