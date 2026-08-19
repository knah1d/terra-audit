/**
 * Thin server-side fetch wrapper for calling the FastAPI backend.
 * Only ever called from Route Handlers / Server Components — the browser
 * never talks to the backend directly (see lib/session.ts and the plan's
 * auth-flow rationale: httpOnly cookie, forwarded as a Bearer header here).
 */

const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

export class BackendError extends Error {
  status: number;
  body: unknown;

  constructor(status: number, body: unknown) {
    super(
      typeof body === "object" && body !== null && "detail" in body
        ? String((body as { detail: unknown }).detail)
        : `Backend request failed with status ${status}`,
    );
    this.status = status;
    this.body = body;
  }
}

export async function backendFetch<T>(
  path: string,
  options: {
    method?: string;
    token?: string | null;
    json?: unknown;
    headers?: Record<string, string>;
    cache?: RequestCache;
  } = {},
): Promise<T> {
  const { method = "GET", token, json, headers = {}, cache } = options;

  const res = await fetch(`${BACKEND_URL}${path}`, {
    method,
    headers: {
      ...(json !== undefined ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
    body: json !== undefined ? JSON.stringify(json) : undefined,
    cache,
  });

  if (res.status === 204) {
    return undefined as T;
  }

  const contentType = res.headers.get("content-type") ?? "";
  const body = contentType.includes("application/json") ? await res.json() : await res.text();

  if (!res.ok) {
    throw new BackendError(res.status, body);
  }
  return body as T;
}
