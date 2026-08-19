import { Leaf } from "lucide-react";
import { getSession } from "@/lib/session";
import { SidebarNav } from "./SidebarNav";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const session = await getSession();

  return (
    <div className="flex min-h-screen">
      <aside className="glass-chrome sticky top-0 flex h-screen w-64 flex-col rounded-none border-y-0 border-l-0 p-4">
        <div className="mb-6 flex items-center gap-2.5 px-2">
          <div className="flex size-7 items-center justify-center rounded-md bg-brand-600 text-white shadow-xs">
            <Leaf className="size-4" />
          </div>
          <span className="font-semibold tracking-tight text-text-primary">Terra Audit</span>
        </div>
        <SidebarNav session={session} />
      </aside>
      <main className="flex-1 p-8">{children}</main>
    </div>
  );
}
