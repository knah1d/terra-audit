"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { PenSquare, Save } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useToast } from "@/components/ui/Toast";
import { useForm, useWatch } from "react-hook-form";
import { GeometryInputTabs } from "@/components/fields/GeometryInputTabs";
import { GeometryPreviewMap } from "@/components/map";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ErrorText, FieldLabel, Select, TextInput } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { NewProjectSheet } from "@/components/projects/NewProjectSheet";
import { useCreateField } from "@/hooks/use-fields";
import { useAssignFieldToProject, useProjects } from "@/hooks/use-projects";
import { useComputedArea, useDetectedDistrict, useDetectedLandUse } from "@/hooks/use-geometry";
import {
  FIELD_TYPE_OPTIONS, LAND_USE_OPTIONS, SUGGESTED_METHODOLOGY, fieldCreateSchema, type FieldCreateForm,
} from "@/lib/schemas/field";
import { firstStepPath } from "@/lib/field-steps";
import { RoleGate } from "@/components/ui/RoleGate";

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
  const { data: districtData, isFetching: detectingDistrict } = useDetectedDistrict(pendingFeature);
  const detectedDistrict = districtData?.district ?? null;
  const {
    data: landUseData, isFetching: detectingLandUse, isError: landUseFailed,
  } = useDetectedLandUse(pendingFeature);
  const detectedLandUse = landUseData?.land_use ?? null;
  const createField = useCreateField();
  const toast = useToast();
  // Project or standalone. "?mode=project" asks for a project; "?project=<id>"
  // (from a project page) pre-selects it.
  const search = useSearchParams();
  const projects = useProjects();
  const projectMode = !!search.get("project") || search.get("mode") === "project";
  const [projectId, setProjectId] = useState(() => search.get("project") ?? "");
  const [projectStart, setProjectStart] = useState(() => new Date().toISOString().slice(0, 10));
  const [creatingProject, setCreatingProject] = useState(false);
  const [savedFieldPath, setSavedFieldPath] = useState<string | null>(null);
  const assignToProject = useAssignFieldToProject(projectId || undefined);

  const {
    register,
    handleSubmit,
    setValue,
    control,
    getFieldState,
    formState: { errors, isSubmitting },
  } = useForm<FieldCreateForm>({
    resolver: zodResolver(fieldCreateSchema),
    defaultValues: { field_type: "rice_awd", land_use: "" },
  });
  const landUse = useWatch({ control, name: "land_use" });
  const fieldType = useWatch({ control, name: "field_type" });
  const suggestedMethodology = SUGGESTED_METHODOLOGY[landUse];

  // The district comes from the boundary and is read-only; manual entry is
  // only offered when the boundary lies outside Bangladesh (null).
  useEffect(() => {
    setValue("district", detectedDistrict ?? "", { shouldValidate: !!detectedDistrict });
  }, [detectedDistrict, setValue]);

  // Field Type (observed land use) is pre-filled from satellite detection
  // but stays editable — unless the user already picked one themselves.
  useEffect(() => {
    if (!getFieldState("land_use").isDirty) setValue("land_use", detectedLandUse ?? "");
  }, [detectedLandUse, setValue, getFieldState]);

  // Field Type suggests a Methodology, without overriding an explicit choice.
  useEffect(() => {
    if (suggestedMethodology && !getFieldState("field_type").isDirty) {
      setValue("field_type", suggestedMethodology);
    }
  }, [suggestedMethodology, setValue, getFieldState]);

  async function onSubmit(values: FieldCreateForm) {
    if (!pendingFeature) return;
    try {
      const field = await createField.mutateAsync({
        ...values, land_use: values.land_use || null, feature: pendingFeature,
      });
      const fieldPath = firstStepPath(field.field_id, field.field_type);
      if (projectId) {
        try {
          // Through the shared hook so every project view refreshes.
          await assignToProject.mutateAsync({ field_id: field.field_id, effective_start_date: projectStart });
        } catch (err) {
          setSavedFieldPath(fieldPath);
          toast.error(err, "Field saved, but not added to the project", { label: "Open the field", href: fieldPath });
          return;
        }
      }
      toast.success("Field registered", { description: field.name });
      router.push(fieldPath);
    } catch (err) {
      toast.error(err, "Couldn't register field");
    }
  }

  return (
    <RoleGate allow={["admin", "analyst"]} fallback={<div className="ui-container"><p className="ui-secondary">You have view-only access. Ask an analyst or administrator to make this change.</p></div>}>
    <div className="ui-container">
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
              <FieldLabel htmlFor="field-1">Field ID</FieldLabel>
              <TextInput id="field-1" aria-invalid={!!errors.field_id} aria-describedby={errors.field_id ? "new-field-field_id-error" : undefined} {...register("field_id")} />
              <ErrorText id="new-field-field_id-error">{errors.field_id?.message}</ErrorText>
            </div>
            <div>
              <FieldLabel htmlFor="field-2">Field Name</FieldLabel>
              <TextInput id="field-2" aria-invalid={!!errors.name} aria-describedby={errors.name ? "new-field-name-error" : undefined} {...register("name")} />
              <ErrorText id="new-field-name-error">{errors.name?.message}</ErrorText>
            </div>
            <div>
              <FieldLabel htmlFor="field-3">District</FieldLabel>
              <TextInput id="field-3" readOnly={detectingDistrict || !!detectedDistrict} placeholder={detectingDistrict ? "Detecting from boundary…" : undefined} aria-invalid={!!errors.district} aria-describedby={errors.district ? "new-field-district-error" : undefined} {...register("district")} />
              {!detectingDistrict && districtData && (
                <p className="ui-meta mt-1">
                  {detectedDistrict
                    ? "Detected from the field boundary."
                    : "Boundary is outside Bangladesh — enter the district manually."}
                </p>
              )}
              <ErrorText id="new-field-district-error">{errors.district?.message}</ErrorText>
            </div>
            <div>
              <FieldLabel htmlFor="field-5">Field Type</FieldLabel>
              <Select id="field-5" {...register("land_use")}>
                <option value="">{detectingLandUse ? "Detecting from satellite imagery…" : "Not set"}</option>
                {LAND_USE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </Select>
              {!detectingLandUse && (
                <p className="ui-meta mt-1">
                  {landUseFailed
                    ? "Satellite detection is unavailable — choose the field type manually."
                    : landUseData && (
                        <>
                          {landUseData.evidence.summary}{" "}
                          {detectedLandUse
                            ? landUse === detectedLandUse
                              ? "Detected from satellite imagery — change it if it's wrong."
                              : "Changed from the detected value — recorded as a manual entry."
                            : "Choose the field type manually."}
                        </>
                      )}
                </p>
              )}
            </div>
            <div>
              <FieldLabel htmlFor="field-4">Methodology</FieldLabel>
              <Select id="field-4" {...register("field_type")}>
                {FIELD_TYPE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </Select>
              <p className="ui-meta mt-1">
                Immutable after creation — determines which methodology (and which subsequent
                data-entry tabs) this field uses.
              </p>
            </div>
            {suggestedMethodology && suggestedMethodology !== fieldType && (
              <Alert tone="warning">
                This methodology doesn&apos;t match the field type (
                {LAND_USE_OPTIONS.find((o) => o.value === landUse)?.label}), which usually uses{" "}
                {FIELD_TYPE_OPTIONS.find((o) => o.value === suggestedMethodology)?.label}.
              </Alert>
            )}
            {landUse === "non_cropland" && (
              <Alert tone="warning">
                This boundary doesn&apos;t look like cropland — check it before registering.
              </Alert>
            )}
            <div>
              <FieldLabel htmlFor="field-project">Project</FieldLabel>
              <Select id="field-project" value={projectId} onChange={(e) => setProjectId(e.target.value)}>
                <option value="">{projectMode ? "Select a project" : "Standalone (no project)"}</option>
                {(projects.data ?? []).filter((p) => p.can_manage).map((p) => <option key={p.project_id} value={p.project_id}>{p.name}</option>)}
              </Select>
              <Button type="button" variant="ghost" size="sm" className="mt-1" onClick={() => setCreatingProject(true)}>+ Create a new project</Button>
              {projectId && (
                <label className="mt-2 block text-sm">In the project from
                  <TextInput type="date" value={projectStart} onChange={(e) => setProjectStart(e.target.value)} />
                </label>
              )}
            </div>
            {savedFieldPath && <Alert tone="warning">The field was saved. <Link className="underline" href={savedFieldPath}>Open the field</Link> to add it to a project.</Alert>}
            <Button type="submit" icon={Save} loading={isSubmitting} disabled={!areaData || detectingDistrict || (projectMode && !projectId) || !!savedFieldPath} className="w-full">
              Save Field
            </Button>
          </form>
        </Card>
      )}
      <NewProjectSheet open={creatingProject} onClose={() => setCreatingProject(false)} onCreated={(p) => setProjectId(p.project_id)} />
    </div>
    </RoleGate>
  );
}
