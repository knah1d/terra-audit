"use client";

import { Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { RoleGate } from "@/components/ui/RoleGate";
import { useDeleteField } from "@/hooks/use-fields";

export function DeleteFieldButton({ fieldId, fieldName }: { fieldId: string; fieldName: string }) {
  const [confirming, setConfirming] = useState(false);
  const router = useRouter();
  const deleteField = useDeleteField();

  async function handleDelete() {
    await deleteField.mutateAsync(fieldId);
    router.push("/fields");
  }

  return (
    <RoleGate allow={["admin"]}>
      {confirming ? (
        <div className="flex items-center gap-2 text-sm text-text-secondary">
          <span>Delete {fieldName}?</span>
          <Button variant="danger" size="sm" loading={deleteField.isPending} onClick={handleDelete}>
            Yes, delete
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setConfirming(false)}>
            Cancel
          </Button>
        </div>
      ) : (
        <Button variant="secondary" size="sm" icon={Trash2} onClick={() => setConfirming(true)}>
          Remove field
        </Button>
      )}
    </RoleGate>
  );
}
