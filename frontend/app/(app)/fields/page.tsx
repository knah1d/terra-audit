"use client";

import Link from "next/link";
import { useFields } from "@/hooks/use-fields";
import { Card } from "@/components/ui/Card";

const FIELD_TYPE_LABELS: Record<string, string> = {
  rice_awd: "Rice — AWD (VM0051)",
  cropland_alm_vm0042: "Cropland — ALM (VM0042)",
};

export default function FieldsPage() {
  const { data: fields, isLoading, error } = useFields();

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Fields</h1>
        <Link href="/fields/new" className="text-sm font-medium text-blue-600 hover:underline">
          + Register a field
        </Link>
      </div>

      {isLoading && <p className="text-sm text-gray-500">Loading…</p>}
      {error && <p className="text-sm text-red-600">Failed to load fields: {error.message}</p>}

      {fields && fields.length === 0 && (
        <Card className="text-center text-sm text-gray-500">
          No fields registered yet.{" "}
          <Link href="/fields/new" className="text-blue-600 hover:underline">
            Register your first field
          </Link>
          .
        </Card>
      )}

      <div className="grid gap-3">
        {fields?.map((field) => (
          <Link key={field.field_id} href={`/fields/${field.field_id}/ledger`}>
            <Card className="flex items-center justify-between transition-shadow hover:shadow-md">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm text-gray-500">{field.field_id}</span>
                  <span className="font-medium">{field.name}</span>
                </div>
                <p className="text-sm text-gray-500">
                  📍 {field.district} · {FIELD_TYPE_LABELS[field.field_type] ?? field.field_type}
                </p>
              </div>
              <span className="font-mono text-sm tabular-nums text-gray-700">
                {field.area_ha?.toFixed(2) ?? "—"} ha
              </span>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
