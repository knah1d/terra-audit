"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { TeamUserOut, UserRole } from "@/types/api";

export function useTeamUsers() {
  return useQuery({
    queryKey: ["team-users"],
    queryFn: () => apiFetch<TeamUserOut[]>("/team/users"),
  });
}

export function useCreateTeamUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; password: string; role: UserRole }) =>
      apiFetch<TeamUserOut>("/team/users", { method: "POST", json: body }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["team-users"] });
    },
  });
}
