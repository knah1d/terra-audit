"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { TextInput, PasswordInput } from "@/components/ui/Field";
export default function AccountAccessPage() {
  const [token, setToken] = useState(""); const [email, setEmail] = useState(""); const [password, setPassword] = useState("");
  const [notice, setNotice] = useState(""); const [error, setError] = useState(""); const [busy, setBusy] = useState(false); const [done, setDone] = useState(false);
  useEffect(() => {
    const t = new URLSearchParams(window.location.hash.slice(1)).get("token");
    if (t) { setToken(t); window.history.replaceState(null, "", window.location.pathname); }
  }, []);
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      const response = await fetch(`/api/auth/recovery/${token ? "consume" : "request"}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(token ? { token, password } : { email }) });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Check your details and try again");
      setNotice(result.message); if (token) { setDone(true); setToken(""); setPassword(""); }
    } catch (e) { setError(e instanceof Error ? e.message : "Request failed"); } finally { setBusy(false); }
  }
  return <div className="mx-auto max-w-md space-y-4 p-6"><h1 className="text-2xl font-semibold">{token ? "Set your password" : "Account recovery"}</h1>
    {notice && <p role="status">{notice}</p>}{error && <p role="alert" className="text-danger-700">{error}</p>}
    {!done && <form className="space-y-4" onSubmit={submit}>{token ? <label className="block text-sm">New password (at least 12 characters)<PasswordInput required minLength={12} maxLength={72} autoComplete="new-password" value={password} onChange={e => setPassword(e.target.value)} /></label> : <label className="block text-sm">Account email<TextInput type="email" required autoComplete="email" value={email} onChange={e => setEmail(e.target.value)} /></label>}
      <Button type="submit" loading={busy}>{token ? "Save password" : "Send recovery link"}</Button></form>}
    <Link href="/login" className="block text-sm text-brand-700">Back to sign in</Link>
  </div>;
}
