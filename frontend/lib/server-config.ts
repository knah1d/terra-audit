import "server-only";

/** Read at request time so builds do not require runtime service variables. */
export function getBackendUrl(): string {
  const production = process.env.NODE_ENV === "production" || process.env.VERCEL === "1";
  const value = process.env.BACKEND_URL?.trim();
  if (!value && production) throw new Error("BACKEND_URL is required in production");
  const raw = value || "http://127.0.0.1:8000";
  let url: URL;
  try { url = new URL(raw); }
  catch { throw new Error("BACKEND_URL must be an absolute backend origin"); }
  const host = url.hostname.toLowerCase();
  const local = host === "localhost" || host.endsWith(".localhost") || host === "127.0.0.1" || host === "[::1]" || host === "0.0.0.0";
  if (!["http:", "https:"].includes(url.protocol) || url.username || url.password ||
      url.search || url.hash || url.pathname !== "/" ||
      (production && (local || (process.env.VERCEL === "1" && url.protocol !== "https:")))) {
    throw new Error("BACKEND_URL must be a backend origin; Vercel requires HTTPS and production forbids localhost");
  }
  return url.origin;
}
