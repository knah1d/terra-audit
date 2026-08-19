import Link from "next/link";
import { notFound } from "next/navigation";
import { DeleteFieldButton } from "@/components/fields/DeleteFieldButton";
import { FieldProvider } from "@/components/fields/FieldContext";
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
      <div className="mb-6 flex items-start justify-between border-b border-gray-200 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm text-gray-500">{field.field_id}</span>
            <h1 className="text-xl font-semibold">{field.name}</h1>
          </div>
          <p className="text-sm text-gray-500">
            📍 {field.district} · {FIELD_TYPE_LABELS[field.field_type] ?? field.field_type} ·{" "}
            {field.area_ha?.toFixed(2)} ha
          </p>
          <nav className="mt-2 flex gap-4 text-sm">
            <Link href={`/fields/${field.field_id}/ledger`} className="text-blue-600 hover:underline">
              Carbon Asset Ledger
            </Link>
            {field.field_type === "cropland_alm_vm0042" && (
              <Link
                href={`/fields/${field.field_id}/practice-data`}
                className="text-blue-600 hover:underline"
              >
                Practice &amp; Soil Data
              </Link>
            )}
            <Link href={`/fields/${field.field_id}/edit`} className="text-blue-600 hover:underline">
              Edit
            </Link>
          </nav>
        </div>
        <DeleteFieldButton fieldId={field.field_id} fieldName={field.name} />
      </div>
      {children}
    </FieldProvider>
  );
}
