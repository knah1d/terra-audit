import { redirect } from "next/navigation";

// The legacy quick preview is replaced by the one-click Calculations page;
// old links land there.
export default async function LedgerRedirect({ params }: { params: Promise<{ fieldId: string }> }) {
  const { fieldId } = await params;
  redirect(`/fields/${fieldId}/calculations`);
}
