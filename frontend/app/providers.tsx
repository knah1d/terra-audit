"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { createContext, useContext, useState } from "react";
import { ToastProvider } from "@/components/ui/Toast";
import { AppearanceProvider } from "@/components/ui/AppearanceProvider";
import type { SessionClaims } from "@/lib/session";

const SessionContext = createContext<SessionClaims | null>(null);

export function useSession() {
  return useContext(SessionContext);
}

export function Providers({
  session,
  children,
}: {
  session: SessionClaims | null;
  children: React.ReactNode;
}) {
  // Remount the entire account-data boundary before rendering a new identity.
  // An effect would run after children had already read the previous cache.
  const identity = session ? `${session.org_id}:${session.user_id}` : "anonymous";
  return <AccountProviders key={identity} session={session}>{children}</AccountProviders>;
}

function AccountProviders({ session, children }: {
  session: SessionClaims | null;
  children: React.ReactNode;
}) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 30_000, retry: 1 },
        },
      }),
  );

  return (
    <ThemeProvider attribute="data-theme" defaultTheme="system" enableSystem disableTransitionOnChange
      storageKey={session ? `terra-audit:theme:${session.org_id}:${session.user_id}` : "terra-audit:theme:anonymous"}>
      <AppearanceProvider authenticated={Boolean(session)}>
      <SessionContext.Provider value={session}>
        <QueryClientProvider client={queryClient}>
          {/* Mounted once at the root so a toast fired right before a
           * navigation (e.g. delete-field's redirect to /fields) still
           * has a container to render into. */}
          <ToastProvider>{children}</ToastProvider>
        </QueryClientProvider>
      </SessionContext.Provider>
      </AppearanceProvider>
    </ThemeProvider>
  );
}
