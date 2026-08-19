import { notFound } from "next/navigation";
import { DeleteFieldButton } from "@/components/fields/DeleteFieldButton";
import { FieldProvider } from "@/components/fields/FieldContext";
import { FieldTabs } from "@/components/fields/FieldTabs";
import { Badge } from "@/components/ui/Badge";
import { backendFetch, BackendError } from "@/lib/backend";
import { getSessionToken } from "@/lib/session";
import type { FieldDetailOut } from "@/types/api";

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
      <div className="mb-6 border-b border-border pb-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-semibold tracking-tight text-text-primary">{field.name}</h1>
              <span className="font-mono text-xs text-text-tertiary">{field.field_id}</span>
            </div>
            <div className="mt-1.5 flex items-center gap-2 text-sm text-text-secondary">
              <span>{field.district}</span>
              <span className="text-text-tertiary">·</span>
              <Badge tone="brand">{FIELD_TYPE_LABELS[field.field_type] ?? field.field_type}</Badge>
              <span className="text-text-tertiary">·</span>
              <span className="font-mono tabular-nums">{field.area_ha?.toFixed(2)} ha</span>
            </div>
          </div>
          <DeleteFieldButton fieldId={field.field_id} fieldName={field.name} />
        </div>
        <div className="mt-4">
          <FieldTabs fieldId={field.field_id} fieldType={field.field_type} />
        </div>
      </div>
      {children}
    </FieldProvider>
  );
}
