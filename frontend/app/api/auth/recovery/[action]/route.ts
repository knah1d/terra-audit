import { NextRequest, NextResponse } from "next/server";
const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";
export async function POST(request: NextRequest, { params }: { params: Promise<{ action: string }> }) {
  const { action } = await params;
  if (!["request", "consume"].includes(action)) return NextResponse.json({ detail: "Not found" }, { status: 404 });
  const body = await request.text();
  if (body.length > 4096) return NextResponse.json({ detail: "Request too large" }, { status: 413 });
  try {
    const response = await fetch(`${BACKEND_URL}/auth/recovery/${action}`, { method: "POST", headers: { "Content-Type": "application/json" }, body, cache: "no-store" });
    return new NextResponse(await response.text(), { status: response.status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ detail: "Account service unavailable" }, { status: 503 });
  }
}
