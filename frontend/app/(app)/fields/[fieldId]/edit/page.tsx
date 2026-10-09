"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Save } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { useFieldContext } from "@/components/fields/FieldContext";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ErrorText, FieldLabel, TextInput } from "@/components/ui/Field";
import { useUpdateField } from "@/hooks/use-fields";
import { useDetectedDistrict } from "@/hooks/use-geometry";
import { ApiError } from "@/lib/api";
import { fieldUpdateSchema, type FieldUpdateForm } from "@/lib/schemas/field";

export default function EditFieldPage() {
  const field = useFieldContext();
  const router = useRouter();
  const updateField = useUpdateField(field.field_id);
  const [serverError, setServerError] = useState<string | null>(null);
  const { data: districtData, isFetching: detectingDistrict } = useDetectedDistrict(field.geojson_geometry);
  const detectedDistrict = districtData?.district ?? null;

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<FieldUpdateForm>({
    resolver: zodResolver(fieldUpdateSchema),
    defaultValues: { name: field.name, district: field.district },
  });

  // The boundary is immutable, so a detected district is read-only (and
  // replaces any older manually-entered value on save).
  useEffect(() => {
    if (detectedDistrict) setValue("district", detectedDistrict, { shouldValidate: true });
  }, [detectedDistrict, setValue]);

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
    <div className="ui-container-narrow">
      <Card>
        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
          <div>
            <FieldLabel htmlFor="field-1">Field Name</FieldLabel>
            <TextInput id="field-1" {...register("name")} />
            <ErrorText>{errors.name?.message}</ErrorText>
          </div>
          <div>
            <FieldLabel htmlFor="field-2">District</FieldLabel>
            <TextInput id="field-2" readOnly={detectingDistrict || !!detectedDistrict} {...register("district")} />
            {detectedDistrict && <p className="ui-meta mt-1">Detected from the field boundary.</p>}
            <ErrorText>{errors.district?.message}</ErrorText>
          </div>
          <p className="ui-meta">
            Field type and boundary are not editable here — they determine which cached data
            belongs to this field. Remove and re-register to change either.
          </p>
          {serverError && <Alert tone="danger">{serverError}</Alert>}
          <Button type="submit" icon={Save} loading={isSubmitting} disabled={detectingDistrict}>
            Save
          </Button>
        </form>
      </Card>
    </div>
  );
}
