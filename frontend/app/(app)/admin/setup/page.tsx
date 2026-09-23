"use client";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { RoleGate } from "@/components/ui/RoleGate";
interface Setup { checks: { name: string; ready: boolean; detail: string }[]; counts: Record<string, number>; queued_jobs: number; notice: string }
export default function SetupPage() {
  const query = useQuery({ queryKey: ["product-readiness"], queryFn: () => apiFetch<Setup>("/admin/product-readiness") });
  return <RoleGate allow={["admin"]}><div className="mx-auto max-w-3xl space-y-4"><h1 className="text-xl font-semibold">Product setup</h1>
    {query.isLoading && <p>Loading setup status…</p>}{query.error && <p role="alert">{query.error.message}</p>}
    <Card><h2 className="font-medium">Start your first project</h2><ol className="mt-3 list-inside list-decimal space-y-2 text-sm"><li><Link className="text-brand-700" href="/team">Invite teammates</Link>, then assign their project roles.</li><li><Link className="text-brand-700" href="/projects">Create a project</Link> and assign registered fields.</li><li>Add crop seasons, practices, attachments, and independent field observations.</li><li>Collect satellite evidence from the project monitoring page.</li><li>Review labels, train and evaluate a crop model in the AI workspace.</li><li>Prepare calculations and submit them through the review workflow.</li></ol></Card>
    {query.data && <><Card><h2 className="font-medium">Configuration</h2>{query.data.checks.map(c => <div className="border-t border-border py-3 text-sm" key={c.name}><strong>{c.ready ? "Configured" : "Needs attention"} · {c.name}</strong><p className="text-text-secondary">{c.detail}</p></div>)}<p className="text-xs text-text-secondary">{query.data.notice}</p></Card><Card><h2 className="font-medium">Organization progress</h2><div className="mt-3 grid grid-cols-2 gap-2 text-sm">{Object.entries(query.data.counts).map(([k, v]) => <p key={k}>{k.replaceAll("_", " ")}: {v}</p>)}</div><p className="mt-3 text-sm">Queued or running jobs: {query.data.queued_jobs}</p><Link href="/admin/queue" className="text-sm text-brand-700">View worker and queue status</Link></Card></>}
  </div></RoleGate>;
}
