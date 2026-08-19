import { NextRequest, NextResponse } from "next/server";
import { backendFetch, BackendError } from "@/lib/backend";
import { SESSION_COOKIE } from "@/lib/session";

/**
 * Proxies login to FastAPI, then sets the returned JWT as an httpOnly
 * cookie itself — the browser never sees or handles the raw token. This
 * keeps FastAPI a plain JWT-issuing API (reusable by non-browser clients
 * later) while Next.js owns the browser-security decision.
 */
export async function POST(request: NextRequest) {
  const body = await request.json();

  try {
    const { access_token } = await backendFetch<{ access_token: string }>("/auth/login", {
      method: "POST",
      json: body,
    });

    const response = NextResponse.json({ ok: true });
    response.cookies.set(SESSION_COOKIE, access_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 60 * 60 * 12, // 12h, matches backend JWT_EXPIRE_MINUTES default
    });
    return response;
  } catch (err) {
    if (err instanceof BackendError) {
      return NextResponse.json({ detail: err.message }, { status: err.status });
    }
    return NextResponse.json({ detail: "Login failed" }, { status: 500 });
  }
}
