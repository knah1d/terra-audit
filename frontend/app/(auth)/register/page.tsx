"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, Leaf } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { Alert } from "@/components/ui/Alert";
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
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-2.5">
          <div className="flex size-10 items-center justify-center rounded-lg bg-brand-600 text-white shadow-sm">
            <Leaf className="size-5" />
          </div>
          <span className="font-semibold tracking-tight text-text-primary">Terra Audit</span>
        </div>
        <div className="glass-chrome-strong rounded-xl p-8">
          <h1 className="mb-1 text-lg font-semibold text-text-primary">
            {step === "details" ? "Create your organization" : "Verify your email"}
          </h1>
          <p className="mb-6 text-sm text-text-secondary">
            {step === "details"
              ? "Sign up to start tracking carbon credits."
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
              {serverError && <Alert tone="danger">{serverError}</Alert>}
              <Button type="submit" loading={detailsForm.formState.isSubmitting} className="w-full">
                Send verification code
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
              {serverError && <Alert tone="danger">{serverError}</Alert>}
              <Button type="submit" loading={otpForm.formState.isSubmitting} className="w-full">
                Verify &amp; create account
              </Button>
              <div className="flex items-center justify-between text-sm">
                <button
                  type="button"
                  onClick={() => setStep("details")}
                  className="inline-flex items-center gap-1 text-text-secondary hover:text-text-primary"
                >
                  <ArrowLeft className="size-3.5" />
                  Different email
                </button>
                <button
                  type="button"
                  onClick={resend}
                  disabled={cooldown > 0}
                  className="font-medium text-brand-600 hover:text-brand-700 disabled:cursor-not-allowed disabled:text-text-tertiary"
                >
                  {cooldown > 0 ? `Resend (${cooldown}s)` : "Resend code"}
                </button>
              </div>
            </form>
          )}

          <p className="mt-6 text-sm text-text-secondary">
            Already have an account?{" "}
            <Link href="/login" className="font-medium text-brand-600 hover:text-brand-700">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </main>
  );
}
