"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Leaf } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Alert } from "@/components/ui/Alert";
import { BotanicalMotif } from "@/components/ui/BotanicalMotif";
import { Button } from "@/components/ui/Button";
import { ErrorText, FieldLabel, PasswordInput, TextInput } from "@/components/ui/Field";

const loginSchema = z.object({
  email: z.string().min(1, "Email is required"),
  password: z.string().min(1, "Password is required"),
});
type LoginForm = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const searchParams = useSearchParams();
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginForm>({ resolver: zodResolver(loginSchema) });

  async function onSubmit(values: LoginForm) {
    setServerError(null);
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(values),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      setServerError(body.detail ?? "Login failed");
      return;
    }
    const next = searchParams.get("next");
    window.location.replace(next?.startsWith("/") && !next.startsWith("//") ? next : "/dashboard");
  }

  return (
    <main className="relative flex min-h-screen flex-1 items-center justify-center overflow-hidden px-4">
      <BotanicalMotif
        size="lg"
        className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2"
      />
      <div className="relative w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-2.5">
          <div className="flex size-10 items-center justify-center rounded-lg bg-brand-600 text-white shadow-glow-sm">
            <Leaf className="size-5" />
          </div>
          <span className="font-semibold tracking-tight text-text-primary">Terra Audit</span>
        </div>
        <div className="glass-chrome-strong rounded-xl p-8">
          <h1 className="ui-page-title mb-2">Sign in</h1>
          <p className="mb-6 text-sm text-text-secondary">Use your organization&apos;s credentials to continue.</p>
          <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
            <div>
              <FieldLabel htmlFor="field-1">Email</FieldLabel>
              <TextInput id="field-1" type="email" autoComplete="email" {...register("email")} />
              <ErrorText>{errors.email?.message}</ErrorText>
            </div>
            <div>
              <FieldLabel htmlFor="field-2">Password</FieldLabel>
              <PasswordInput id="field-2" autoComplete="current-password" {...register("password")} />
              <ErrorText>{errors.password?.message}</ErrorText>
            </div>
            {serverError && <Alert tone="danger">{serverError}</Alert>}
            <Button type="submit" loading={isSubmitting} className="w-full">
              Sign in
            </Button>
          </form>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-x-4 gap-y-2 text-sm text-text-secondary">
            <Link href="/account-access" className="font-medium text-brand-600 hover:text-brand-700">
              Forgot password?
            </Link>
            <p>
              Need an account?{" "}
              <Link href="/register" className="font-medium text-brand-600 hover:text-brand-700">
                Create one
              </Link>
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}
