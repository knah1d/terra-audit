"use client";

import { AlertCircle, FolderKanban, MapPin, Plus } from "lucide-react";
import Link from "next/link";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { IconTile } from "@/components/ui/IconTile";
import { PageHeader } from "@/components/ui/PageHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import { useFields } from "@/hooks/use-fields";

const FIELD_TYPE_LABELS: Record<string, string> = {
  rice_awd: "Rice — AWD (VM0051)",
  cropland_alm_vm0042: "Cropland — ALM (VM0042)",
};

export default function FieldsPage() {
  const { data: fields, isLoading, error } = useFields();

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader
        title="Fields"
        subtitle="Registered field boundaries and their carbon-credit methodology."
        actions={
          <Link href="/fields/new">
            <Button icon={Plus} size="sm">
              Register a field
            </Button>
          </Link>
        }
      />

      {isLoading && (
        <div className="grid gap-3">
          <Skeleton className="h-[68px]" />
          <Skeleton className="h-[68px]" />
          <Skeleton className="h-[68px]" />
        </div>
      )}

      {error && (
        <Alert tone="danger" title="Failed to load fields">
          {error.message}
        </Alert>
      )}

      {fields && fields.length === 0 && (
        <EmptyState
          icon={FolderKanban}
          motif
          title="No fields registered yet"
          description="Register your first field boundary to start tracking carbon credits."
          action={
            <Link href="/fields/new">
              <Button icon={Plus} size="sm">
                Register a field
              </Button>
            </Link>
          }
        />
      )}

      <div className="grid gap-3">
        {fields?.map((field, i) => (
          <Link
            key={field.field_id}
            href={`/fields/${field.field_id}/ledger`}
            className="enter"
            style={{ animationDelay: `${Math.min(i, 8) * 30}ms` }}
          >
            <Card interactive className="flex items-center justify-between p-4">
              <div className="flex items-center gap-3">
                <IconTile icon={FolderKanban} />
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-text-primary">{field.name}</span>
                    <span className="font-mono text-xs text-text-tertiary">{field.field_id}</span>
                  </div>
                  <div className="mt-0.5 flex items-center gap-2 text-sm text-text-secondary">
                    <span className="inline-flex items-center gap-1">
                      <MapPin className="size-3.5" />
                      {field.district}
                    </span>
                    <Badge tone="brand">{FIELD_TYPE_LABELS[field.field_type] ?? field.field_type}</Badge>
                  </div>
                </div>
              </div>
              <span className="font-mono text-sm tabular-nums text-text-secondary">
                {field.area_ha?.toFixed(2) ?? <AlertCircle className="size-4 text-text-tertiary" />} ha
              </span>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
