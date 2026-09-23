import { notFound } from "next/navigation";
import { ProjectProvider } from "@/components/projects/ProjectContext";
import { ProjectTabs } from "@/components/projects/ProjectTabs";
import { Badge } from "@/components/ui/Badge";
import { backendFetch, BackendError } from "@/lib/backend";
import { getSessionToken } from "@/lib/session";
import type { ProjectOut } from "@/types/api";

export default async function ProjectLayout({
  children, params,
}: {
  children: React.ReactNode;
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const token = await getSessionToken();

  let project: ProjectOut;
  try {
    project = await backendFetch<ProjectOut>(`/projects/${projectId}`, { token, cache: "no-store" });
  } catch (err) {
    if (err instanceof BackendError && (err.status === 404 || err.status === 403)) notFound();
    throw err;
  }

  return (
    <ProjectProvider project={project}>
      <div className="mb-6 border-b border-border pb-4">
        <div className="flex items-center gap-2">
          <h1 className="text-xl font-semibold tracking-tight text-text-primary">{project.name}</h1>
          <Badge tone="brand">{project.status}</Badge>
        </div>
        {project.description && <p className="mt-1 text-sm text-text-secondary">{project.description}</p>}
        <div className="mt-4">
          <ProjectTabs projectId={project.project_id} />
        </div>
      </div>
      {children}
    </ProjectProvider>
  );
}
