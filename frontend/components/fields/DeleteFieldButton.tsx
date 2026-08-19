"use client";

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
        <div className="flex items-center gap-2 text-sm">
          <span>Delete {fieldName}? This cannot be undone.</span>
          <Button variant="danger" onClick={handleDelete} disabled={deleteField.isPending}>
            Yes, delete
          </Button>
          <Button variant="secondary" onClick={() => setConfirming(false)}>
            Cancel
          </Button>
        </div>
      ) : (
        <Button variant="danger" onClick={() => setConfirming(true)}>
          🗑️ Remove field
        </Button>
      )}
    </RoleGate>
  );
}
