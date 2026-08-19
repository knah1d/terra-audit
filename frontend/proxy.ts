import { NextRequest, NextResponse } from "next/server";
import { SESSION_COOKIE } from "@/lib/session";

/**
 * Checks only for cookie PRESENCE, not signature validity — real
 * verification happens on every actual backend request (a forged/expired
 * token just gets a 401 there, surfaced by the client's error handling).
 * This proxy exists purely so an unauthenticated visit to an (app)/*
 * route redirects to /login immediately, not after a failed fetch.
 * (Named `proxy.ts`/`proxy()`, not `middleware.ts`/`middleware()` — that
 * convention was renamed in Next.js 16; this repo is on 16.3.1.)
 */
export function proxy(request: NextRequest) {
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  const isLoginPage = request.nextUrl.pathname.startsWith("/login");

  if (!token && !isLoginPage) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", request.nextUrl.pathname);
    return NextResponse.redirect(loginUrl);
  }
  if (token && isLoginPage) {
    return NextResponse.redirect(new URL("/fields", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
