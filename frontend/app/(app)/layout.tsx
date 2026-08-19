import { Leaf } from "lucide-react";
import { getSession } from "@/lib/session";
import { SidebarNav } from "./SidebarNav";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const session = await getSession();

  return (
    <div className="flex min-h-screen gap-3 p-3">
      {/* Floating shell, not edge-flush: margin on every side (the outer
       * flex gap + padding above), rounded on all four corners, sitting
       * above the ambient layer as its own elevated glass panel — this is
       * the single change that reads most as "Apple app" vs. "web
       * dashboard," where a full-height flush sidebar is the norm. */}
      <aside className="glass-chrome-strong sticky top-3 z-chrome flex h-[calc(100vh-1.5rem)] w-64 shrink-0 flex-col rounded-2xl p-4">
        <div className="mb-6 flex items-center gap-2.5 px-2">
          <div className="flex size-7 items-center justify-center rounded-md bg-brand-600 text-white shadow-xs">
            <Leaf className="size-4" />
          </div>
          <span className="font-semibold tracking-tight text-text-primary">Terra Audit</span>
        </div>
        <SidebarNav session={session} />
      </aside>
      <main className="min-w-0 flex-1 p-5">{children}</main>
    </div>
  );
}
