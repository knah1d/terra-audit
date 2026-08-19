"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { createContext, useContext, useState } from "react";
import { ToastProvider } from "@/components/ui/Toast";
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
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 30_000, retry: 1 },
        },
      }),
  );

  return (
    <ThemeProvider attribute="data-theme" defaultTheme="system" enableSystem>
      <SessionContext.Provider value={session}>
        <QueryClientProvider client={queryClient}>
          {/* Mounted once at the root so a toast fired right before a
           * navigation (e.g. delete-field's redirect to /fields) still
           * has a container to render into. */}
          <ToastProvider>{children}</ToastProvider>
        </QueryClientProvider>
      </SessionContext.Provider>
    </ThemeProvider>
  );
}
