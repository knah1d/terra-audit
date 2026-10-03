"use client";

import { LogOut } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/Button";

export function LogoutButton() {
  const queryClient = useQueryClient();
  async function handleLogout() {
    const response = await fetch("/api/auth/logout", { method: "POST" });
    if (!response.ok) return;
    await queryClient.cancelQueries();
    queryClient.clear();
    // Also discard Next's cached authenticated routes and local component state.
    window.location.replace("/login");
  }
  return (
    <Button variant="secondary" size="sm" icon={LogOut} className="w-full" onClick={handleLogout}>
      Log out
    </Button>
  );
}
