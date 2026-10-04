"use client";

import dynamic from "next/dynamic";

// Recovery tokens arrive in the URL fragment, which is only available in
// the browser. Mount the form there instead of syncing it after SSR.
const AccountAccessForm = dynamic(() => import("@/components/auth/AccountAccessForm"), {
  ssr: false,
  loading: () => <p role="status" className="p-6">Loading account recovery…</p>,
});

export default function AccountAccessPage() {
  return <AccountAccessForm />;
}
