"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Leaf } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { ErrorText, FieldLabel, TextInput } from "@/components/ui/Field";

const loginSchema = z.object({
  email: z.string().min(1, "Email is required"),
  password: z.string().min(1, "Password is required"),
});
type LoginForm = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const router = useRouter();
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
    router.push(searchParams.get("next") ?? "/fields");
    router.refresh();
  }

  return (
    <main className="flex min-h-screen flex-1 items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-2.5">
          <div className="flex size-10 items-center justify-center rounded-lg bg-brand-600 text-white shadow-sm">
            <Leaf className="size-5" />
          </div>
          <span className="font-semibold tracking-tight text-text-primary">Terra Audit</span>
        </div>
        <div className="glass-chrome-strong rounded-xl p-8">
          <h1 className="mb-1 text-lg font-semibold text-text-primary">Sign in</h1>
          <p className="mb-6 text-sm text-text-secondary">Use your organization&apos;s credentials to continue.</p>
          <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
            <div>
              <FieldLabel>Email</FieldLabel>
              <TextInput type="email" autoComplete="email" {...register("email")} />
              <ErrorText>{errors.email?.message}</ErrorText>
            </div>
            <div>
              <FieldLabel>Password</FieldLabel>
              <TextInput type="password" autoComplete="current-password" {...register("password")} />
              <ErrorText>{errors.password?.message}</ErrorText>
            </div>
            {serverError && <Alert tone="danger">{serverError}</Alert>}
            <Button type="submit" loading={isSubmitting} className="w-full">
              Sign in
            </Button>
          </form>
          <p className="mt-6 text-sm text-text-secondary">
            Need an account?{" "}
            <Link href="/register" className="font-medium text-brand-600 hover:text-brand-700">
              Create one
            </Link>
          </p>
        </div>
      </div>
    </main>
  );
}
