import { Pencil } from "lucide-react";
import { notFound } from "next/navigation";
import { DeleteFieldButton } from "@/components/fields/DeleteFieldButton";
import { FieldProvider } from "@/components/fields/FieldContext";
import { FieldProjectControl } from "@/components/fields/FieldProjectControl";
import { FieldTabs } from "@/components/fields/FieldTabs";
import { StepNav } from "@/components/fields/StepNav";
import { Badge } from "@/components/ui/Badge";
import { ButtonLink } from "@/components/ui/Button";
import { backendFetch, BackendError } from "@/lib/backend";
import { getSessionToken } from "@/lib/session";
import type { FieldDetailOut } from "@/types/api";
import { RoleGate } from "@/components/ui/RoleGate";

const FIELD_TYPE_LABELS: Record<string, string> = {
  rice_awd: "Rice — AWD (VM0051)",
  cropland_alm_vm0042: "Cropland — ALM (VM0042)",
};

export default async function FieldLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ fieldId: string }>;
}) {
  const { fieldId } = await params;
  const token = await getSessionToken();

  let field: FieldDetailOut;
  try {
    field = await backendFetch<FieldDetailOut>(`/fields/${fieldId}`, { token, cache: "no-store" });
  } catch (err) {
    if (err instanceof BackendError && err.status === 404) notFound();
    throw err;
  }

  return (
    <FieldProvider field={field}>
      <div className="ui-container mb-6 border-b border-border-subtle pb-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="ui-page-title">{field.name}</h1>
              <span className="font-mono text-xs text-text-tertiary">{field.field_id}</span>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-text-secondary">
              <span>{field.district}</span>
              <span className="text-text-tertiary">·</span>
              <Badge tone="brand">{FIELD_TYPE_LABELS[field.field_type] ?? field.field_type}</Badge>
              <span className="text-text-tertiary">·</span>
              <span className="font-mono tabular-nums">{field.area_ha?.toFixed(2)} ha</span>
              <span className="text-text-tertiary">·</span>
              <FieldProjectControl fieldId={field.field_id} project={field.current_project ?? null} />
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <RoleGate allow={["admin", "analyst"]}>
              <ButtonLink href={`/fields/${field.field_id}/edit`} variant="secondary" size="sm" icon={Pencil}>
                Edit
              </ButtonLink>
            </RoleGate>
            <DeleteFieldButton fieldId={field.field_id} fieldName={field.name} />
          </div>
        </div>
        <div className="mt-4">
          <FieldTabs fieldId={field.field_id} fieldType={field.field_type} />
        </div>
      </div>
      {children}
      <StepNav fieldId={field.field_id} fieldType={field.field_type} />
    </FieldProvider>
  );
}
