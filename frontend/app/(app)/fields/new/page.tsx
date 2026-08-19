"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { GeometryInputTabs } from "@/components/fields/GeometryInputTabs";
import { GeometryPreviewMap } from "@/components/map";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ErrorText, FieldLabel, Select, TextInput } from "@/components/ui/Field";
import { useCreateField } from "@/hooks/use-fields";
import { useComputedArea } from "@/hooks/use-geometry";
import { FIELD_TYPE_OPTIONS, fieldCreateSchema, type FieldCreateForm } from "@/lib/schemas/field";
import { ApiError } from "@/lib/api";

/**
 * The "pending geometry" concept — the direct client-side replacement for
 * Streamlit's st.session_state["pending_field_geom"] — lives as plain
 * component state here rather than a global store: it's scoped to this
 * one page/flow and never needed elsewhere in the tree.
 */
export default function NewFieldPage() {
  const router = useRouter();
  const [pendingFeature, setPendingFeature] = useState<GeoJSON.Feature | null>(null);
  const { data: areaData } = useComputedArea(pendingFeature);
  const createField = useCreateField();
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FieldCreateForm>({
    resolver: zodResolver(fieldCreateSchema),
    defaultValues: { field_type: "rice_awd" },
  });

  async function onSubmit(values: FieldCreateForm) {
    if (!pendingFeature) return;
    setServerError(null);
    try {
      const field = await createField.mutateAsync({ ...values, feature: pendingFeature });
      router.push(`/fields/${field.field_id}/ledger`);
    } catch (err) {
      setServerError(err instanceof ApiError ? err.detail : "Failed to save field");
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-6 text-2xl font-semibold">Register a Field</h1>

      <Card className="mb-6">
        {pendingFeature ? (
          <div>
            <GeometryPreviewMap feature={pendingFeature} />
            <div className="mt-2 flex items-center justify-between text-sm">
              <span className="text-gray-500">
                Computed area: <strong>{areaData ? `${areaData.area_ha.toFixed(4)} ha` : "…"}</strong>
              </span>
              <button
                type="button"
                onClick={() => setPendingFeature(null)}
                className="text-blue-600 hover:underline"
              >
                Redraw / choose a different boundary
              </button>
            </div>
          </div>
        ) : (
          <GeometryInputTabs onGeometry={setPendingFeature} />
        )}
      </Card>

      {pendingFeature && (
        <Card>
          <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
            <div>
              <FieldLabel>Field ID</FieldLabel>
              <TextInput {...register("field_id")} />
              <ErrorText>{errors.field_id?.message}</ErrorText>
            </div>
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
            <div>
              <FieldLabel>Field Type / Methodology</FieldLabel>
              <Select {...register("field_type")}>
                {FIELD_TYPE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </Select>
              <p className="mt-1 text-xs text-gray-500">
                Immutable after creation — determines which methodology (and which subsequent
                data-entry tabs) this field uses.
              </p>
            </div>
            {serverError && <p className="text-sm text-red-600">{serverError}</p>}
            <Button type="submit" disabled={isSubmitting || !areaData} className="w-full">
              {isSubmitting ? "Saving…" : "💾 Save Field"}
            </Button>
          </form>
        </Card>
      )}
    </div>
  );
}
