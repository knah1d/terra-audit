"use client";

import { Eye, EyeOff } from "lucide-react";
import { InputHTMLAttributes, SelectHTMLAttributes, TextareaHTMLAttributes, useState } from "react";

export function FieldLabel({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <label className={`mb-1.5 block text-sm font-medium text-text-primary ${className}`}>{children}</label>;
}

// field-inset gives text fields a light-mode top highlight (same specular
// idea as .glass-chrome's rim, scaled down) so they read as a recessed
// surface rather than a flat box — see app/globals.css. The focus ring is
// a soft glow (shadow, not a hard outline) that grows in on focus — the
// same "soft glowing snap" most modern text fields use instead of a flat
// 2px outline appearing/disappearing with no transition.
const FIELD_BASE =
  "field-inset w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary transition-[border-color,box-shadow] duration-[var(--dur-base)] ease-[var(--curve-out)] focus:border-brand-600 focus:shadow-[0_0_0_4px_var(--brand-100)] focus:outline-none disabled:bg-surface-muted disabled:text-text-tertiary";

export function TextInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`${FIELD_BASE} ${props.className ?? ""}`} />;
}

// Same field-inset styling as TextInput, plus a show/hide toggle — for
// every password field (login, register, team invite) instead of a bare
// type="password" input.
export function PasswordInput(props: InputHTMLAttributes<HTMLInputElement>) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <input
        {...props}
        type={visible ? "text" : "password"}
        className={`${FIELD_BASE} pr-10 ${props.className ?? ""}`}
      />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        tabIndex={-1}
        aria-label={visible ? "Hide password" : "Show password"}
        className="absolute inset-y-0 right-0 flex w-9 items-center justify-center text-text-tertiary transition-colors hover:text-text-secondary"
      >
        {visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
      </button>
    </div>
  );
}

export function TextArea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={`${FIELD_BASE} font-mono ${props.className ?? ""}`} />;
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={`${FIELD_BASE} ${props.className ?? ""}`} />;
}

export function ErrorText({ children }: { children?: string }) {
  if (!children) return null;
  return <p className="mt-1 text-xs text-danger-600">{children}</p>;
}
