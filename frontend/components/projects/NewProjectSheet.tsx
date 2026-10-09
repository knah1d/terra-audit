"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { TextArea, TextInput } from "@/components/ui/Field";
import { Sheet } from "@/components/ui/Sheet";
import { useCreateProject } from "@/hooks/use-projects";
import type { ProjectOut } from "@/types/api";

/** The single "create a project" form — used by the Projects page and the
 * first-run Get Started screen. */
export function NewProjectSheet({ open, onClose, onCreated }: {
  open: boolean;
  onClose: () => void;
  onCreated?: (project: ProjectOut) => void;
}) {
  const create = useCreateProject();
  const [error, setError] = useState("");

  return (
    <Sheet open={open} onClose={onClose} title="New project">
      <form className="flex flex-col gap-3" onSubmit={(e) => {
        e.preventDefault();
        setError("");
        const data = new FormData(e.currentTarget);
        create.mutateAsync({
          name: data.get("name"), description: data.get("description"), geography: data.get("geography"),
        }).then((project) => { onClose(); onCreated?.(project); })
          .catch((err) => setError(err instanceof Error ? err.message : "Failed to create project"));
      }}>
        <label className="text-sm">Name<TextInput name="name" required maxLength={200} /></label>
        <label className="text-sm">Description<TextArea name="description" maxLength={4000} /></label>
        <label className="text-sm">Geography<TextInput name="geography" placeholder="e.g. Rajshahi division" maxLength={2000} /></label>
        {error && <p role="alert" className="text-sm text-danger-700">{error}</p>}
        <Button type="submit" loading={create.isPending}>Create project</Button>
        <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
      </form>
    </Sheet>
  );
}
