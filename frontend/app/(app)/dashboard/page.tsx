"use client";

import { FolderKanban, MapPin, Plus, Rows3, Sprout } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useSession } from "@/app/providers";
import { NewProjectSheet } from "@/components/projects/NewProjectSheet";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { IconTile } from "@/components/ui/IconTile";
import { PageHeader } from "@/components/ui/PageHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import { useFields } from "@/hooks/use-fields";
import { useOrgSummary, useProjects } from "@/hooks/use-projects";

const METHODOLOGY: Record<string, string> = { rice_awd: "Rice — AWD", cropland_alm_vm0042: "Cropland — ALM" };
const newestFirst = <T extends { created_at: string | null }>(rows: T[]) =>
  [...rows].sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""));

/** Post-login landing page. An organisation with no fields and no projects
 * (counted organisation-wide, from saved data) sees Get Started; everyone
 * else sees the dashboard. */
export default function DashboardPage() {
  const summary = useOrgSummary();
  if (summary.isLoading) return <div className="ui-container"><Skeleton className="h-48" /></div>;
  if (summary.error || !summary.data) {
    return <div className="ui-container"><Alert tone="danger" title="Unable to load your workspace">{summary.error?.message}</Alert></div>;
  }
  return summary.data.is_new_organization ? <GetStarted /> : <Dashboard />;
}

function GetStarted() {
  const router = useRouter();
  const session = useSession();
  const [creating, setCreating] = useState(false);
  const canCreate = session?.role === "admin" || session?.role === "analyst";

  return (
    <div className="ui-container max-w-4xl">
      <PageHeader title="Welcome to Terra Audit" subtitle="How would you like to start?" />
      {!canCreate && (
        <Alert tone="info" className="mb-4">Ask an admin or analyst in your organisation to create the first project or field.</Alert>
      )}
      <div className="grid gap-4 md:grid-cols-2">
        <Card className="flex flex-col gap-4">
          <IconTile icon={Rows3} size="lg" />
          <div>
            <h2 className="ui-subsection-title">Create a Carbon Project</h2>
            <p className="ui-secondary mt-1">For NGOs, organisations and project developers. Group fields, monitor them, calculate and send results for internal review.</p>
          </div>
          <Button className="mt-auto" icon={Plus} disabled={!canCreate} onClick={() => setCreating(true)}>Create a project</Button>
        </Card>
        <Card className="flex flex-col gap-4">
          <IconTile icon={Sprout} size="lg" />
          <div>
            <h2 className="ui-subsection-title">Analyze a Standalone Field</h2>
            <p className="ui-secondary mt-1">For individuals, research and testing. Register one field and get satellite analysis and a preliminary estimate.</p>
          </div>
          {canCreate
            ? <ButtonLink className="mt-auto" variant="secondary" href="/fields/new" icon={MapPin}>Register a field</ButtonLink>
            : <Button className="mt-auto" variant="secondary" icon={MapPin} disabled>Register a field</Button>}
        </Card>
      </div>
      <p className="ui-meta mt-4 text-center">A standalone field can be added to a project later — its data carries over.</p>
      <NewProjectSheet open={creating} onClose={() => setCreating(false)}
        onCreated={(project) => router.push(`/projects/${encodeURIComponent(project.project_id)}`)} />
    </div>
  );
}

function Dashboard() {
  const router = useRouter();
  const session = useSession();
  const projects = useProjects();
  const fields = useFields();
  const [creating, setCreating] = useState(false);
  const canCreate = session?.role === "admin" || session?.role === "analyst";
  const recentProjects = newestFirst(projects.data ?? []).slice(0, 5);
  const recentFields = newestFirst(fields.data ?? []).slice(0, 5);

  return (
    <div className="ui-container">
      <PageHeader
        title="Dashboard"
        actions={canCreate && <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="secondary" icon={Plus} onClick={() => setCreating(true)}>New project</Button>
          <ButtonLink size="sm" href="/fields/new" icon={MapPin}>Register a field</ButtonLink>
        </div>}
      />
      <div className="grid gap-6 lg:grid-cols-2">
        <section>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="ui-subsection-title">Recent projects</h2>
            <Link className="ui-meta underline" href="/projects">All projects</Link>
          </div>
          {projects.isLoading ? <Skeleton className="h-24" /> : !recentProjects.length ? (
            <Card><p className="ui-secondary">No projects yet.</p></Card>
          ) : (
            <div className="grid gap-2">
              {recentProjects.map((p) => (
                <Link key={p.project_id} href={`/projects/${encodeURIComponent(p.project_id)}`}>
                  <Card interactive className="flex items-center justify-between gap-3">
                    <span className="flex min-w-0 items-center gap-3">
                      <IconTile icon={FolderKanban} size="sm" />
                      <span className="truncate font-medium">{p.name}</span>
                    </span>
                    <Badge tone="brand">{p.status}</Badge>
                  </Card>
                </Link>
              ))}
            </div>
          )}
        </section>
        <section>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="ui-subsection-title">Recent fields</h2>
            <Link className="ui-meta underline" href="/fields">All fields</Link>
          </div>
          {fields.isLoading ? <Skeleton className="h-24" /> : !recentFields.length ? (
            <Card><p className="ui-secondary">No fields yet.</p></Card>
          ) : (
            <div className="grid gap-2">
              {recentFields.map((f) => (
                <Link key={f.field_id} href={`/fields/${encodeURIComponent(f.field_id)}`}>
                  <Card interactive className="flex items-center justify-between gap-3">
                    <span className="flex min-w-0 items-center gap-3">
                      <IconTile icon={MapPin} size="sm" />
                      <span className="min-w-0">
                        <span className="block truncate font-medium">{f.name}</span>
                        <span className="ui-meta">{f.district}</span>
                      </span>
                    </span>
                    <Badge tone="neutral">{METHODOLOGY[f.field_type] ?? f.field_type}</Badge>
                  </Card>
                </Link>
              ))}
            </div>
          )}
        </section>
      </div>
      <NewProjectSheet open={creating} onClose={() => setCreating(false)}
        onCreated={(project) => router.push(`/projects/${encodeURIComponent(project.project_id)}`)} />
    </div>
  );
}
