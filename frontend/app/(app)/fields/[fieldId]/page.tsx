import { notFound, redirect } from "next/navigation";
import { backendFetch, BackendError } from "@/lib/backend";
import { getSessionToken } from "@/lib/session";
import type { FieldDetailOut } from "@/types/api";

// The field's "home" tab, mirroring Streamlit's tab order: rice_awd fields
// land on Signal Analytics (you run the SAR pipeline before the ledger has
// real data to calculate from); ALM fields go straight to the ledger,
// which itself gates on Practice & Soil Data completeness.
export default async function FieldIndexPage({
  params,
}: {
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

  redirect(
    field.field_type === "rice_awd" ? `/fields/${fieldId}/signal-analytics` : `/fields/${fieldId}/ledger`,
  );
}
