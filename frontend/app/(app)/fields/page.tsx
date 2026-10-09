"use client";

import { AlertCircle, FolderKanban, MapPin, Plus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { TextInput, Select } from "@/components/ui/Field";
import { filterFields } from "@/lib/field-filters";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button, ButtonLink } from "@/components/ui/Button";
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

  const [query, setQuery] = useState("");
  const [methodology, setMethodology] = useState("all");
  const [sort, setSort] = useState("name");
  const [scope, setScope] = useState<"all" | "standalone" | "project">("all");
  const visibleFields = filterFields(fields ?? [], query, methodology, sort)
    .filter((f) => scope === "all" || (scope === "project") === !!f.current_project);

  return (
    <div className="ui-container">
      <PageHeader
        title="Fields"
        actions={
          <div className="flex flex-wrap gap-2">
            <ButtonLink href="/fields/new" variant="secondary" icon={Plus}>Register standalone field</ButtonLink>
            <ButtonLink href="/fields/new?mode=project" icon={Plus}>Register project field</ButtonLink>
          </div>
        }
      />

      {!!fields?.length && (
        <div className="ui-card mb-6">
          <div className="mb-3 flex flex-wrap gap-2" role="group" aria-label="Field type">
            {([["all", "All fields"], ["standalone", "Standalone"], ["project", "In a project"]] as const).map(([value, label]) => (
              <Button key={value} size="sm" variant={scope === value ? "primary" : "secondary"} aria-pressed={scope === value} onClick={() => setScope(value)}>
                {label} ({(fields ?? []).filter((f) => value === "all" || (value === "project") === !!f.current_project).length})
              </Button>
            ))}
          </div>
          <div className="grid gap-3 sm:grid-cols-[1fr_180px_150px]">
            <label className="ui-label">Find a field
              <TextInput className="mt-2" type="search" placeholder="Search name, district or ID…" value={query} onChange={(e) => setQuery(e.target.value)} />
            </label>
            <label className="ui-label">Methodology
              <Select className="mt-2" value={methodology} onChange={(e) => setMethodology(e.target.value)}>
                <option value="all">All methodologies</option><option value="rice_awd">Rice AWD</option><option value="cropland_alm_vm0042">Cropland ALM</option>
              </Select>
            </label>
            <label className="ui-label">Sort by
              <Select className="mt-2" value={sort} onChange={(e) => setSort(e.target.value)}>
                <option value="name">Name A–Z</option><option value="area">Largest area</option><option value="newest">Newest first</option>
              </Select>
            </label>
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-text-secondary">
            <span role="status">{visibleFields.length} of {fields.length} fields</span>
            {(query || methodology !== "all" || sort !== "name" || scope !== "all") && <Button variant="ghost" size="sm" onClick={() => { setQuery(""); setMethodology("all"); setSort("name"); setScope("all"); }}>Clear filters</Button>}
          </div>
        </div>
      )}
      {!!fields?.length && visibleFields.length === 0 && <EmptyState icon={FolderKanban} title="No matching fields" description="Try another search or clear your filters." />}

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
          description="Register a standalone field for analysis, or a field inside a carbon project."
          action={
            <ButtonLink href="/fields/new" icon={Plus}>Register a field</ButtonLink>
          }
        />
      )}

      <div className="grid gap-3">
        {visibleFields.map((field, i) => (
          <Link
            key={field.field_id}
            href={`/fields/${field.field_id}`}
            className="enter rounded-lg"
            style={{ animationDelay: `${Math.min(i, 8) * 30}ms` }}
          >
            <Card interactive className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <IconTile icon={FolderKanban} />
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium text-text-primary">{field.name}</span>
                    <span className="font-mono text-xs text-text-tertiary">{field.field_id}</span>
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-text-secondary">
                    <span className="inline-flex items-center gap-1">
                      <MapPin className="size-3.5" />
                      {field.district}
                    </span>
                    <Badge tone="brand">{FIELD_TYPE_LABELS[field.field_type] ?? field.field_type}</Badge>
                    <Badge tone="neutral">{field.current_project ? `Project: ${field.current_project.name}` : "Standalone"}</Badge>
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
