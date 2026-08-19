"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { Button } from "@/components/ui/Button";
import { ErrorText, FieldLabel, TextInput } from "@/components/ui/Field";
import {
  registerDetailsSchema,
  verifyOtpSchema,
  type RegisterDetailsForm,
  type VerifyOtpForm,
} from "@/lib/schemas/registration";

export default function RegisterPage() {
  const router = useRouter();
  const [step, setStep] = useState<"details" | "otp">("details");
  const [email, setEmail] = useState("");
  const [serverError, setServerError] = useState<string | null>(null);
  const [cooldown, setCooldown] = useState(0);

  const detailsForm = useForm<RegisterDetailsForm>({ resolver: zodResolver(registerDetailsSchema) });
  const otpForm = useForm<VerifyOtpForm>({ resolver: zodResolver(verifyOtpSchema) });

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setInterval(() => setCooldown((c) => Math.max(0, c - 1)), 1000);
    return () => clearInterval(timer);
  }, [cooldown]);

  async function requestOtp(values: RegisterDetailsForm) {
    setServerError(null);
    const res = await fetch("/api/auth/register/request-otp", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(values),
    });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      setServerError(body.detail ?? "Could not send verification code");
      return;
    }
    setEmail(body.email);
    setCooldown(60); // matches backend's OTP_RESEND_COOLDOWN_SECONDS default
    setStep("otp");
  }

  async function verifyOtp(values: VerifyOtpForm) {
    setServerError(null);
    const res = await fetch("/api/auth/register/verify-otp", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, otp: values.otp }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      setServerError(body.detail ?? "Verification failed");
      return;
    }
    router.push("/fields");
    router.refresh();
  }

  async function resend() {
    if (cooldown > 0) return;
    await requestOtp(detailsForm.getValues());
  }

  return (
    <main className="flex min-h-screen flex-1 items-center justify-center px-4">
      <div className="w-full max-w-sm rounded-lg border border-gray-200 bg-white p-8 shadow-sm">
        <h1 className="mb-1 text-xl font-semibold">🌍 Terra Audit</h1>
        <p className="mb-6 text-sm text-gray-500">
          {step === "details"
            ? "Create a new organization account."
            : `Enter the 6-digit code sent to ${email}.`}
        </p>

        {step === "details" && (
          <form onSubmit={detailsForm.handleSubmit(requestOtp)} className="flex flex-col gap-4">
            <div>
              <FieldLabel>Organization name</FieldLabel>
              <TextInput autoComplete="organization" {...detailsForm.register("org_name")} />
              <ErrorText>{detailsForm.formState.errors.org_name?.message}</ErrorText>
            </div>
            <div>
              <FieldLabel>Email</FieldLabel>
              <TextInput type="email" autoComplete="email" {...detailsForm.register("email")} />
              <ErrorText>{detailsForm.formState.errors.email?.message}</ErrorText>
            </div>
            <div>
              <FieldLabel>Password</FieldLabel>
              <TextInput
                type="password"
                autoComplete="new-password"
                {...detailsForm.register("password")}
              />
              <ErrorText>{detailsForm.formState.errors.password?.message}</ErrorText>
            </div>
            {serverError && <p className="text-sm text-red-600">{serverError}</p>}
            <Button type="submit" disabled={detailsForm.formState.isSubmitting} className="w-full">
              {detailsForm.formState.isSubmitting ? "Sending code…" : "Send verification code"}
            </Button>
          </form>
        )}

        {step === "otp" && (
          <form onSubmit={otpForm.handleSubmit(verifyOtp)} className="flex flex-col gap-4">
            <div>
              <FieldLabel>6-digit code</FieldLabel>
              <TextInput
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                placeholder="000000"
                className="text-center font-mono text-lg tracking-widest"
                {...otpForm.register("otp")}
              />
              <ErrorText>{otpForm.formState.errors.otp?.message}</ErrorText>
            </div>
            {serverError && <p className="text-sm text-red-600">{serverError}</p>}
            <Button type="submit" disabled={otpForm.formState.isSubmitting} className="w-full">
              {otpForm.formState.isSubmitting ? "Verifying…" : "Verify & create account"}
            </Button>
            <button
              type="button"
              onClick={resend}
              disabled={cooldown > 0}
              className="text-sm text-blue-600 hover:underline disabled:cursor-not-allowed disabled:text-gray-400"
            >
              {cooldown > 0 ? `Resend code (${cooldown}s)` : "Resend code"}
            </button>
            <button
              type="button"
              onClick={() => setStep("details")}
              className="text-sm text-gray-500 hover:underline"
            >
              &larr; Use a different email
            </button>
          </form>
        )}

        <p className="mt-6 text-sm text-gray-500">
          Already have an account?{" "}
          <Link href="/login" className="text-blue-600 hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </main>
  );
}
