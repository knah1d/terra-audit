import { NextRequest, NextResponse } from "next/server";
import { getSessionToken } from "@/lib/session";

import { getBackendUrl } from "@/lib/server-config";

// Authenticated project data must not be stored by browsers or shared CDNs.
const PRIVATE_HEADERS = {
  "Cache-Control": "private, no-store, max-age=0",
  "CDN-Cache-Control": "no-store",
  "Vercel-CDN-Cache-Control": "no-store",
  Vary: "Cookie",
};

/**
 * Generic authenticated proxy: every client-side TanStack Query call goes
 * through /api/proxy/* rather than the FastAPI backend directly, so the
 * httpOnly session cookie (never readable by client JS) can be forwarded
 * as an Authorization: Bearer header here. One catch-all route instead of
 * hand-writing a Next.js route per FastAPI endpoint — this file is pure
 * plumbing, it has no knowledge of what any given path means.
 *
 * Passes through the request body and a small allowlist of headers
 * (Content-Type, Idempotency-Key) verbatim, so both JSON requests and the
 * one multipart file-upload endpoint (/fields/parse/upload) work
 * unmodified.
 */
async function proxy(request: NextRequest, path: string[]) {
  const token = await getSessionToken();
  if (!token) {
    return NextResponse.json({ detail: "Not authenticated" }, { status: 401, headers: PRIVATE_HEADERS });
  }

  const search = request.nextUrl.search;
  const targetUrl = `${getBackendUrl()}/${path.join("/")}${search}`;

  const forwardHeaders: Record<string, string> = { Authorization: `Bearer ${token}` };
  const contentType = request.headers.get("content-type");
  if (contentType) forwardHeaders["Content-Type"] = contentType;
  const idempotencyKey = request.headers.get("idempotency-key");
  if (idempotencyKey) forwardHeaders["Idempotency-Key"] = idempotencyKey;

  const hasBody = !["GET", "HEAD", "DELETE"].includes(request.method);

  const res = await fetch(targetUrl, {
    method: request.method,
    headers: forwardHeaders,
    body: hasBody ? await request.arrayBuffer() : undefined,
    cache: "no-store",
  });

  // 204/205/304 are "null body" statuses per the Fetch spec — constructing
  // a Response/NextResponse with ANY body (even an empty ArrayBuffer)
  // alongside one of these throws a TypeError. That crashed this route
  // handler AFTER the backend had already committed (e.g. a field
  // DELETE succeeding server-side at 204, but the client seeing a 500
  // because this proxy itself then threw trying to forward the
  // response) — never forward a body for these.
  if (res.status === 204 || res.status === 205 || res.status === 304) {
    return new NextResponse(null, { status: res.status, headers: PRIVATE_HEADERS });
  }

  const resContentType = res.headers.get("content-type") ?? "";
  if (resContentType.includes("application/json") || resContentType.includes("text/")) {
    const text = await res.text();
    return new NextResponse(text, {
      status: res.status,
      headers: { ...PRIVATE_HEADERS, "content-type": resContentType || "application/json" },
    });
  }
  // Binary (PDF export) — stream through as-is.
  const buffer = await res.arrayBuffer();
  return new NextResponse(buffer, {
    status: res.status,
    headers: { ...PRIVATE_HEADERS, "content-type": resContentType },
  });
}

export async function GET(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return proxy(request, (await params).path);
}
export async function POST(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return proxy(request, (await params).path);
}
export async function PUT(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return proxy(request, (await params).path);
}
export async function PATCH(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return proxy(request, (await params).path);
}
export async function DELETE(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return proxy(request, (await params).path);
}
