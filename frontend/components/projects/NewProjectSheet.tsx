"use client";

import { useToast } from "@/components/ui/Toast";
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
  const toast = useToast();

  return (
    <Sheet open={open} onClose={onClose} title="New project">
      <form className="flex flex-col gap-3" onSubmit={(e) => {
        e.preventDefault();
        const data = new FormData(e.currentTarget);
        create.mutateAsync({
          name: data.get("name"), description: data.get("description"), geography: data.get("geography"),
        }).then((project) => { onClose(); toast.success("Project created", { description: project.name }); onCreated?.(project); })
          .catch((err) => toast.error(err, "Couldn't create project"));
      }}>
        <label className="text-sm">Name<TextInput name="name" required maxLength={200} /></label>
        <label className="text-sm">Description<TextArea name="description" maxLength={4000} /></label>
        <label className="text-sm">Geography<TextInput name="geography" placeholder="e.g. Rajshahi division" maxLength={2000} /></label>
        <Button type="submit" loading={create.isPending}>Create project</Button>
        <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
      </form>
    </Sheet>
  );
}
