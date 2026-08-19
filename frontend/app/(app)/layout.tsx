import Link from "next/link";
import { LogoutButton } from "@/components/fields/LogoutButton";
import { getSession } from "@/lib/session";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const session = await getSession();

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-64 flex-col border-r border-gray-200 bg-white p-4">
        <Link href="/fields" className="mb-6 text-lg font-semibold">
          🌍 Terra Audit
        </Link>
        <nav className="flex flex-col gap-1 text-sm">
          <Link href="/fields" className="rounded-md px-3 py-2 hover:bg-gray-100">
            Fields
          </Link>
          <Link
            href="/fields/new"
            className="rounded-md px-3 py-2 hover:bg-gray-100"
          >
            + Register a field
          </Link>
        </nav>
        <div className="mt-auto border-t border-gray-200 pt-4 text-xs text-gray-500">
          {session && (
            <>
              <p className="truncate">{session.email}</p>
              <p className="mb-2 capitalize">{session.role}</p>
            </>
          )}
          <LogoutButton />
        </div>
      </aside>
      <main className="flex-1 p-8">{children}</main>
    </div>
  );
}
