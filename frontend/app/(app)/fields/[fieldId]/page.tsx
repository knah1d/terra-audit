import { redirect } from "next/navigation";

export default async function FieldIndexPage({
  params,
}: {
  params: Promise<{ fieldId: string }>;
}) {
  const { fieldId } = await params;
  redirect(`/fields/${fieldId}/ledger`);
}
