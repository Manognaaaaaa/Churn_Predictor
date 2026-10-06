import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const API = "http://localhost:8000";
const apiProxy = Object.fromEntries(
  ["/customers", "/portfolio", "/forecast", "/allocate", "/model", "/health"].map((p) => [
    p,
    { target: API, changeOrigin: true },
  ])
);

export default defineConfig({
  plugins: [react()],
  server: { proxy: apiProxy },
});
