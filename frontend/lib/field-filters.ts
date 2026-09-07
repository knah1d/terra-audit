import type { FieldOut, PortfolioEntry } from "@/types/api";

export function filterFields(fields: FieldOut[], query: string, methodology: string, sort: string) {
  const search = query.trim().toLowerCase();
  return fields.filter((field) =>
    (methodology === "all" || field.field_type === methodology) &&
    `${field.name} ${field.district} ${field.field_id}`.toLowerCase().includes(search)
  ).sort((a, b) => {
    if (sort === "area") return (b.area_ha ?? -Infinity) - (a.area_ha ?? -Infinity) || a.name.localeCompare(b.name);
    if (sort === "newest") return (b.created_at ?? "").localeCompare(a.created_at ?? "") || a.name.localeCompare(b.name);
    return a.name.localeCompare(b.name);
  });
}

export type PortfolioSortKey = "name" | "district" | "field_type" | "area_ha" | "final_issuance" | "calculated_at";
export function sortPortfolio(entries: PortfolioEntry[], key: PortfolioSortKey, direction: "asc" | "desc") {
  return [...entries].sort((a, b) => {
    const left = a[key], right = b[key];
    // Missing values stay last in either direction.
    if (left === null) return right === null ? 0 : 1;
    if (right === null) return -1;
    const result = typeof left === "number" && typeof right === "number" ? left - right : String(left).localeCompare(String(right));
    return (direction === "asc" ? result : -result) || a.name.localeCompare(b.name);
  });
}
