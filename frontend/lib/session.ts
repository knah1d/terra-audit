import { cookies } from "next/headers";

export const SESSION_COOKIE = "session";

export type SessionClaims = {
  user_id: string;
  org_id: string;
  email: string;
  role: "admin" | "analyst" | "viewer";
  exp: number;
};

/**
 * Decodes the JWT payload WITHOUT verifying the signature — this is only
 * ever used for UI branching (role-driven conditional rendering), never
 * for an authorization decision. The backend independently verifies the
 * signature on every real request; a forged/tampered token here would
 * just get a 401/403 back from the backend, not grant any actual access.
 */
function decodeClaims(token: string): SessionClaims | null {
  try {
    const [, payloadB64] = token.split(".");
    const json = Buffer.from(payloadB64, "base64").toString("utf-8");
    return JSON.parse(json) as SessionClaims;
  } catch {
    return null;
  }
}

/** Server-only — reads the httpOnly session cookie. Never call from a
 * client component (cookies() is a server API). */
export async function getSessionToken(): Promise<string | null> {
  const store = await cookies();
  return store.get(SESSION_COOKIE)?.value ?? null;
}

export async function getSession(): Promise<SessionClaims | null> {
  const token = await getSessionToken();
  if (!token) return null;
  const claims = decodeClaims(token);
  if (!claims) return null;
  if (claims.exp * 1000 < Date.now()) return null; // expired
  return claims;
}
