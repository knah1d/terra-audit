import { getSession } from "@/lib/session";
import { AppShell } from "./AppShell";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const session = await getSession();
  return <AppShell session={session}>{children}</AppShell>;
}
