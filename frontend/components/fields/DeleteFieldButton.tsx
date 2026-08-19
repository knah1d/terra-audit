"use client";

import { Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { RoleGate } from "@/components/ui/RoleGate";
import { Sheet } from "@/components/ui/Sheet";
import { useToast } from "@/components/ui/Toast";
import { useDeleteField } from "@/hooks/use-fields";

export function DeleteFieldButton({ fieldId, fieldName }: { fieldId: string; fieldName: string }) {
  const [confirming, setConfirming] = useState(false);
  const router = useRouter();
  const deleteField = useDeleteField();
  const { show } = useToast();

  async function handleDelete() {
    await deleteField.mutateAsync(fieldId);
    show(`${fieldName} removed`, "info");
    router.push("/fields");
  }

  return (
    <RoleGate allow={["admin"]}>
      <Button variant="secondary" size="sm" icon={Trash2} onClick={() => setConfirming(true)}>
        Remove field
      </Button>
      <Sheet open={confirming} onClose={() => setConfirming(false)} title="Remove field">
        <p className="mb-5 text-sm text-text-secondary">
          Delete <strong className="text-text-primary">{fieldName}</strong>? This removes its
          boundary, cached signal data, and credit history. This cannot be undone.
        </p>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" size="sm" onClick={() => setConfirming(false)}>
            Cancel
          </Button>
          <Button variant="danger" size="sm" loading={deleteField.isPending} onClick={handleDelete}>
            Yes, delete
          </Button>
        </div>
      </Sheet>
    </RoleGate>
  );
}
