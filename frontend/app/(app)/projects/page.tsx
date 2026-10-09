"use client";

import { FolderKanban, Plus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { NewProjectSheet } from "@/components/projects/NewProjectSheet";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import { useProjects } from "@/hooks/use-projects";

export default function ProjectsPage() {
  const projects = useProjects();
  const [open, setOpen] = useState(false);

  return (
    <div className="ui-container">
      <PageHeader
        title="Projects"
        subtitle="Operational grouping of fields for monitoring and internal review — separate from carbon-claim allocation."
        actions={<Button icon={Plus} size="sm" onClick={() => setOpen(true)}>New project</Button>}
      />
      {projects.isLoading && <Skeleton className="h-24" />}
      {projects.data && projects.data.length === 0 && (
        <EmptyState icon={FolderKanban} motif title="No projects yet" description="Create a project to start assigning fields and monitoring them together."
          action={<Button icon={Plus} onClick={() => setOpen(true)}>New project</Button>} />
      )}
      <div className="grid gap-3">
        {(projects.data ?? []).map((p) => (
          <Link key={p.project_id} href={`/projects/${p.project_id}`}>
            <Card interactive className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="font-medium">{p.name}</p>
                <p className="ui-secondary">{p.description}</p>
              </div>
              <Badge tone="brand">{p.status}</Badge>
            </Card>
          </Link>
        ))}
      </div>

      <NewProjectSheet open={open} onClose={() => setOpen(false)} />
    </div>
  );
}
