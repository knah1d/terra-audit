"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { PortfolioEntry } from "@/types/api";

export function usePortfolio() {
  return useQuery({
    queryKey: ["portfolio"],
    queryFn: () => apiFetch<PortfolioEntry[]>("/portfolio/summary"),
  });
}
