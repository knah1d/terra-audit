"use client";

import { createContext, useContext } from "react";
import type { ProjectOut } from "@/types/api";

const ProjectContext = createContext<ProjectOut | null>(null);

export function ProjectProvider({ project, children }: { project: ProjectOut; children: React.ReactNode }) {
  return <ProjectContext.Provider value={project}>{children}</ProjectContext.Provider>;
}

export function useProjectContext(): ProjectOut {
  const project = useContext(ProjectContext);
  if (!project) throw new Error("useProjectContext() used outside a /projects/[projectId]/* route");
  return project;
}
