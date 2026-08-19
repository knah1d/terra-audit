import { NextRequest, NextResponse } from "next/server";
import { backendFetch, BackendError } from "@/lib/backend";
import { SESSION_COOKIE } from "@/lib/session";

/**
 * Proxies OTP verification, then sets the returned JWT as the same
 * httpOnly session cookie app/api/auth/login/route.ts sets — the user
 * is logged in immediately on a successful verify, no separate login
 * step (they've already proven both password and email control).
 */
export async function POST(request: NextRequest) {
  const body = await request.json();

  try {
    const { access_token } = await backendFetch<{ access_token: string }>(
      "/auth/register/verify-otp",
      { method: "POST", json: body },
    );

    const response = NextResponse.json({ ok: true });
    response.cookies.set(SESSION_COOKIE, access_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 60 * 60 * 12,
    });
    return response;
  } catch (err) {
    if (err instanceof BackendError) {
      return NextResponse.json({ detail: err.message }, { status: err.status });
    }
    return NextResponse.json({ detail: "Verification failed" }, { status: 500 });
  }
}
