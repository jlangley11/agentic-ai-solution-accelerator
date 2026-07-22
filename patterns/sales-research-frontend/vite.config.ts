import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// The dev server proxies scenario, research, and health routes to FastAPI
// process so the browser issues same-origin requests during development —
// no CORS pre-flight required. Override the proxy target with
// VITE_DEV_API_PROXY in `.env` (e.g. point at a remote dev API).
//
// In production (SWA build) the bundle reads `VITE_API_BASE_URL` at build
// time and calls the API directly. The API has to allow the SWA origin via
// the `ALLOWED_ORIGINS` env var (see `src/main.py`); the frontend README
// has the wiring snippet.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_");
  const devApiProxy = (env.VITE_DEV_API_PROXY || "http://localhost:8000").replace(/\/$/, "");

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/research": { target: devApiProxy, changeOrigin: true, secure: false },
        "/scenario": { target: devApiProxy, changeOrigin: true, secure: false },
        "/healthz": { target: devApiProxy, changeOrigin: true, secure: false },
      },
    },
    build: {
      outDir: "dist",
      sourcemap: true,
    },
  };
});
