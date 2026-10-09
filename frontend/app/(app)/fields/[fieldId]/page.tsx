import { notFound, redirect } from "next/navigation";
import { backendFetch, BackendError } from "@/lib/backend";
import { firstStepPath } from "@/lib/field-steps";
import { getSessionToken } from "@/lib/session";
import type { FieldDetailOut } from "@/types/api";

// A field opens on its first workflow step (lib/field-steps.ts), so the
// tab order and every entry point agree on where work starts.
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

  redirect(firstStepPath(fieldId, field.field_type));
}
