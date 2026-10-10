"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Card } from "@/components/ui/Card";
import { Switch } from "@/components/ui/Switch";
import { useToast } from "@/components/ui/Toast";
import { apiFetch } from "@/lib/api";

type Permission = { provider: string; external: boolean; allowed: boolean };

/** Org-wide consent for sending project evidence to the external AI provider
 * that writes explanations ("Why … ?" buttons). Admin only. */
export function AiProviderPermission() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const permission = useQuery({ queryKey: ["ai-provider-permission"], queryFn: () => apiFetch<Permission>("/admin/ai-provider-permission") });
  const update = useMutation({
    mutationFn: (allowed: boolean) => apiFetch("/admin/ai-provider-permission", { method: "PUT", json: { allowed } }),
    onSuccess: (_d, allowed) => {
      void queryClient.invalidateQueries({ queryKey: ["ai-provider-permission"] });
      toast.success(allowed ? "AI explanations enabled" : "AI explanations disabled");
    },
    onError: (e) => toast.error(e, "Couldn't change the AI permission"),
  });
  const data = permission.data;
  if (!data || !data.external) return null;
  const name = data.provider === "groq" ? "Groq" : "OpenAI";
  return (
    <Card className="space-y-2">
      <h2 className="ui-section-title">AI explanations</h2>
      <p className="ui-secondary">
        The &quot;Why …?&quot; buttons (Signal Analytics, AWD Check, Enrollment, Reviews, leakage) send the relevant
        project evidence to {name} to write a cited, draft explanation. Explanations never change a result.
      </p>
      <Switch checked={data.allowed} onChange={(v) => update.mutate(v)}
        label={`Allow sending project evidence to ${name} for explanations`} />
    </Card>
  );
}
