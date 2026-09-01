"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { PenSquare, Save } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { GeometryInputTabs } from "@/components/fields/GeometryInputTabs";
import { GeometryPreviewMap } from "@/components/map";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ErrorText, FieldLabel, Select, TextInput } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
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
      // Mirrors Streamlit's tab order: rice_awd's first working tab is
      // Signal Analytics (you run the SAR pipeline before the ledger has
      // anything real to calculate from); ALM has no such step, so it
      // goes straight to the ledger, which itself gates on Practice &
      // Soil Data completeness.
      router.push(
        field.field_type === "rice_awd"
          ? `/fields/${field.field_id}/signal-analytics`
          : `/fields/${field.field_id}/ledger`,
      );
    } catch (err) {
      setServerError(err instanceof ApiError ? err.detail : "Failed to save field");
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader
        title="Register a Field"
        subtitle="Draw, upload, or paste a boundary, then confirm its details."
      />

      <Card className="mb-6">
        {pendingFeature ? (
          <div>
            <GeometryPreviewMap feature={pendingFeature} />
            <div className="mt-3 flex items-center justify-between text-sm">
              <span className="text-text-secondary">
                Computed area: <strong className="font-mono text-text-primary">{areaData ? `${areaData.area_ha.toFixed(4)} ha` : "…"}</strong>
              </span>
              <button
                type="button"
                onClick={() => setPendingFeature(null)}
                className="inline-flex items-center gap-1 font-medium text-brand-600 hover:text-brand-700"
              >
                <PenSquare className="size-3.5" />
                Redraw
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
              <p className="mt-1 text-xs text-text-tertiary">
                Immutable after creation — determines which methodology (and which subsequent
                data-entry tabs) this field uses.
              </p>
            </div>
            {serverError && <Alert tone="danger">{serverError}</Alert>}
            <Button type="submit" icon={Save} loading={isSubmitting} disabled={!areaData} className="w-full">
              Save Field
            </Button>
          </form>
        </Card>
      )}
    </div>
  );
}
