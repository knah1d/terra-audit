import { NextRequest, NextResponse } from "next/server";
import { backendFetch, BackendError } from "@/lib/backend";

/**
 * Proxies the first step of self-serve signup — no cookie to set here
 * (that happens on verify-otp, once the email is actually confirmed).
 */
export async function POST(request: NextRequest) {
  const body = await request.json();

  try {
    const data = await backendFetch<{ email: string; expires_in_seconds: number }>(
      "/auth/register/request-otp",
      { method: "POST", json: body },
    );
    return NextResponse.json(data);
  } catch (err) {
    if (err instanceof BackendError) {
      return NextResponse.json({ detail: err.message }, { status: err.status });
    }
    return NextResponse.json({ detail: "Could not send verification code" }, { status: 500 });
  }
}
