"use client";

import { createContext, useContext } from "react";
import type { FieldDetailOut } from "@/types/api";

const FieldContext = createContext<FieldDetailOut | null>(null);

export function FieldProvider({
  field,
  children,
}: {
  field: FieldDetailOut;
  children: React.ReactNode;
}) {
  return <FieldContext.Provider value={field}>{children}</FieldContext.Provider>;
}

/** Throws if used outside a field route — every page under
 * fields/[fieldId]/* is guaranteed one by the layout. */
export function useFieldContext(): FieldDetailOut {
  const field = useContext(FieldContext);
  if (!field) throw new Error("useFieldContext() used outside a /fields/[fieldId]/* route");
  return field;
}
