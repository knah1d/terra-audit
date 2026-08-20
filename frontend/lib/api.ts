"use client";

/**
 * Client-side fetch wrapper hitting our own /api/proxy/* route (never the
 * FastAPI backend directly — see app/api/proxy/[...path]/route.ts and the
 * plan's auth-flow rationale). Used by every hooks/use-*.ts TanStack Query
 * hook.
 */
export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

export async function apiFetch<T>(
  path: string,
  options: { method?: string; json?: unknown; headers?: Record<string, string> } = {},
): Promise<T> {
  const { method = "GET", json, headers = {} } = options;
  const res = await fetch(`/api/proxy${path}`, {
    method,
    headers: {
      ...(json !== undefined ? { "Content-Type": "application/json" } : {}),
      ...headers,
    },
    body: json !== undefined ? JSON.stringify(json) : undefined,
  });

  if (res.status === 204) return undefined as T;

  const contentType = res.headers.get("content-type") ?? "";
  const body = contentType.includes("application/json") ? await res.json() : await res.text();

  if (!res.ok) {
    const detail = typeof body === "object" && body && "detail" in body
      ? String((body as { detail: unknown }).detail)
      : `Request failed (${res.status})`;
    throw new ApiError(res.status, detail);
  }
  return body as T;
}

/**
 * apiFetch above always parses the response as JSON/text, which would
 * corrupt binary content — used for the export/pdf endpoint (the proxy
 * already streams binary through untouched, see app/api/proxy's
 * "Binary (PDF export)" comment; this is the client-side counterpart).
 * JSON/CSV exports are text and work fine through apiFetch itself.
 */
export async function apiFetchBlob(path: string): Promise<Blob> {
  const res = await fetch(`/api/proxy${path}`);
  if (!res.ok) {
    const text = await res.text();
    let detail = `Request failed (${res.status})`;
    try {
      const parsed = JSON.parse(text);
      if (parsed && typeof parsed === "object" && "detail" in parsed) detail = String(parsed.detail);
    } catch {
      // not JSON — keep the generic detail
    }
    throw new ApiError(res.status, detail);
  }
  return res.blob();
}
