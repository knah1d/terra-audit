"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Save } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useToast } from "@/components/ui/Toast";
import { useForm, useWatch } from "react-hook-form";
import { useFieldContext } from "@/components/fields/FieldContext";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ErrorText, FieldLabel, Select, TextInput } from "@/components/ui/Field";
import { useUpdateField } from "@/hooks/use-fields";
import { useDetectedDistrict, useDetectedLandUse } from "@/hooks/use-geometry";
import { firstStepPath } from "@/lib/field-steps";
import { LAND_USE_OPTIONS, fieldUpdateSchema, type FieldUpdateForm } from "@/lib/schemas/field";
import { RoleGate } from "@/components/ui/RoleGate";

export default function EditFieldPage() {
  const field = useFieldContext();
  const router = useRouter();
  const updateField = useUpdateField(field.field_id);
  const toast = useToast();
  const { data: districtData, isFetching: detectingDistrict } = useDetectedDistrict(field.geojson_geometry);
  const detectedDistrict = districtData?.district ?? null;
  // Only fields registered before Field Type existed (land_use null) are
  // detected here; a recorded value is shown as-is.
  const {
    data: landUseData, isFetching: detectingLandUse, isError: landUseFailed,
  } = useDetectedLandUse(field.land_use ? null : field.geojson_geometry);
  const detectedLandUse = landUseData?.land_use ?? null;

  const {
    register,
    handleSubmit,
    setValue,
    control,
    getFieldState,
    formState: { errors, isSubmitting },
  } = useForm<FieldUpdateForm>({
    resolver: zodResolver(fieldUpdateSchema),
    defaultValues: { name: field.name, district: field.district, land_use: field.land_use ?? "" },
  });
  const landUse = useWatch({ control, name: "land_use" });

  // The boundary is immutable, so a detected district is read-only (and
  // replaces any older manually-entered value on save).
  useEffect(() => {
    if (detectedDistrict) setValue("district", detectedDistrict, { shouldValidate: true });
  }, [detectedDistrict, setValue]);

  useEffect(() => {
    if (detectedLandUse && !getFieldState("land_use").isDirty) setValue("land_use", detectedLandUse);
  }, [detectedLandUse, setValue, getFieldState]);

  const landUseHint = (() => {
    if (field.land_use) {
      if (landUse !== field.land_use) return "Changed — will be recorded as a manual entry.";
      const summary = field.land_use_evidence?.summary ?? "";
      return field.land_use_source === "detected"
        ? `Detected from satellite imagery. ${summary}`
        : `Entered manually. ${summary ? `Satellite detection: ${summary}` : ""}`;
    }
    if (detectingLandUse) return "Detecting from satellite imagery…";
    if (landUseFailed) return "Satellite detection is unavailable — choose the field type manually.";
    if (!landUseData) return null;
    if (!detectedLandUse) return `${landUseData.evidence.summary ?? ""} Choose the field type manually.`;
    return landUse === detectedLandUse
      ? `${landUseData.evidence.summary ?? ""} Detected from satellite imagery — change it if it's wrong.`
      : "Changed from the detected value — recorded as a manual entry.";
  })();

  async function onSubmit(values: FieldUpdateForm) {
    try {
      await updateField.mutateAsync({ ...values, land_use: values.land_use || null });
      toast.success("Field saved");
      router.push(firstStepPath(field.field_id, field.field_type));
      router.refresh(); // the field header/context come from the server layout
    } catch (err) {
      toast.error(err, "Couldn't save field");
    }
  }

  return (
    <RoleGate allow={["admin", "analyst"]} fallback={<div className="ui-container"><p className="ui-secondary">You have view-only access. Ask an analyst or administrator to make this change.</p></div>}>
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
          <div>
            <FieldLabel htmlFor="field-3">Field Type</FieldLabel>
            <Select id="field-3" {...register("land_use")}>
              <option value="">Not set</option>
              {LAND_USE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </Select>
            {landUseHint && <p className="ui-meta mt-1">{landUseHint}</p>}
          </div>
          <p className="ui-meta">
            Methodology and boundary are not editable here — they determine which cached data
            belongs to this field. Remove and re-register to change either.
          </p>
          <Button type="submit" icon={Save} loading={isSubmitting} disabled={detectingDistrict}>
            Save
          </Button>
        </form>
      </Card>
    </div>
    </RoleGate>
  );
}
