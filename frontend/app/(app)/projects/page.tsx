"use client";

import { FolderKanban, Plus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { TextArea, TextInput } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { Sheet } from "@/components/ui/Sheet";
import { Skeleton } from "@/components/ui/Skeleton";
import { useCreateProject, useProjects } from "@/hooks/use-projects";

export default function ProjectsPage() {
  const projects = useProjects();
  const create = useCreateProject();
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title="Projects"
        subtitle="Operational grouping of fields for monitoring and internal review — separate from carbon-claim allocation."
        actions={<Button icon={Plus} size="sm" onClick={() => setOpen(true)}>New project</Button>}
      />
      {projects.isLoading && <Skeleton className="h-24" />}
      {projects.data && projects.data.length === 0 && (
        <EmptyState icon={FolderKanban} motif title="No projects yet" description="Create a project to start assigning fields and monitoring them together." />
      )}
      <div className="grid gap-3">
        {(projects.data ?? []).map((p) => (
          <Link key={p.project_id} href={`/projects/${p.project_id}`}>
            <Card interactive className="flex items-center justify-between p-4">
              <div>
                <p className="font-medium">{p.name}</p>
                <p className="text-sm text-text-secondary">{p.description}</p>
              </div>
              <Badge tone="brand">{p.status}</Badge>
            </Card>
          </Link>
        ))}
      </div>

      <Sheet open={open} onClose={() => setOpen(false)} title="New project">
        <form className="flex flex-col gap-3" onSubmit={(e) => {
          e.preventDefault();
          setError("");
          const data = new FormData(e.currentTarget);
          create.mutateAsync({
            name: data.get("name"), description: data.get("description"), geography: data.get("geography"),
          }).then(() => setOpen(false)).catch((err) => setError(err instanceof Error ? err.message : "Failed to create project"));
        }}>
          <label className="text-sm">Name<TextInput name="name" required maxLength={200} /></label>
          <label className="text-sm">Description<TextArea name="description" maxLength={4000} /></label>
          <label className="text-sm">Geography<TextInput name="geography" placeholder="e.g. Rajshahi division" maxLength={2000} /></label>
          {error && <p role="alert" className="text-sm text-danger-700">{error}</p>}
          <Button type="submit" loading={create.isPending}>Create project</Button>
        </form>
      </Sheet>
    </div>
  );
}
