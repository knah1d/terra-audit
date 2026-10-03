import { NextRequest, NextResponse } from "next/server";
import { getBackendUrl } from "@/lib/server-config";
export async function POST(request: NextRequest, { params }: { params: Promise<{ action: string }> }) {
  const { action } = await params;
  if (!["request", "consume"].includes(action)) return NextResponse.json({ detail: "Not found" }, { status: 404 });
  const body = await request.text();
  if (body.length > 4096) return NextResponse.json({ detail: "Request too large" }, { status: 413 });
  try {
    const response = await fetch(`${getBackendUrl()}/auth/recovery/${action}`, { method: "POST", headers: { "Content-Type": "application/json" }, body, cache: "no-store" });
    return new NextResponse(await response.text(), { status: response.status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ detail: "Account service unavailable" }, { status: 503 });
  }
}
