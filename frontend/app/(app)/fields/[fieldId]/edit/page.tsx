"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { useFieldContext } from "@/components/fields/FieldContext";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ErrorText, FieldLabel, TextInput } from "@/components/ui/Field";
import { useUpdateField } from "@/hooks/use-fields";
import { ApiError } from "@/lib/api";
import { fieldUpdateSchema, type FieldUpdateForm } from "@/lib/schemas/field";

export default function EditFieldPage() {
  const field = useFieldContext();
  const router = useRouter();
  const updateField = useUpdateField(field.field_id);
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FieldUpdateForm>({
    resolver: zodResolver(fieldUpdateSchema),
    defaultValues: { name: field.name, district: field.district },
  });

  async function onSubmit(values: FieldUpdateForm) {
    setServerError(null);
    try {
      await updateField.mutateAsync(values);
      router.push(`/fields/${field.field_id}/ledger`);
    } catch (err) {
      setServerError(err instanceof ApiError ? err.detail : "Failed to save");
    }
  }

  return (
    <div className="mx-auto max-w-md">
      <Card>
        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
          <div>
            <FieldLabel>Field Name</FieldLabel>
            <TextInput {...register("name")} />
            <ErrorText>{errors.name?.message}</ErrorText>
          </div>
          <div>
            <FieldLabel>District</FieldLabel>
            <TextInput {...register("district")} />
            <ErrorText>{errors.district?.message}</ErrorText>
          </div>
          <p className="text-xs text-gray-500">
            Field type and boundary are not editable here — they determine which cached data
            belongs to this field. Remove and re-register to change either.
          </p>
          {serverError && <p className="text-sm text-red-600">{serverError}</p>}
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Saving…" : "💾 Save"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
