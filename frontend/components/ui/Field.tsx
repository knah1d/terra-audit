"use client";

import { Eye, EyeOff } from "lucide-react";
import { forwardRef, InputHTMLAttributes, LabelHTMLAttributes, TextareaHTMLAttributes, useState } from "react";
import { DatePicker } from "./DatePicker";

export { Select } from "./Select";

export function FieldLabel({
  children,
  className = "",
  ...props
}: LabelHTMLAttributes<HTMLLabelElement>) {
  return <label {...props} className={`ui-label mb-2 block ${className}`}>{children}</label>;
}

// Shared control chrome (44px, 8px radius, 14px text, subtle 2px keyboard
// focus) lives in .ui-control in app/globals.css so custom controls such as
// Select render identically.
const FIELD_BASE = "ui-control";

export const TextInput = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function TextInput(props, ref) {
  if (props.type === "date" || props.type === "datetime-local") return <DatePicker {...props} ref={ref} />;
  return <input {...props} ref={ref} className={`${FIELD_BASE} ${props.className ?? ""}`} />;
});

// Same control styling as TextInput, plus a show/hide toggle — for
// every password field (login, register, team invite) instead of a bare
// type="password" input.
export function PasswordInput(props: InputHTMLAttributes<HTMLInputElement>) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <input
        {...props}
        type={visible ? "text" : "password"}
        className={`${FIELD_BASE} pr-11 ${props.className ?? ""}`}
      />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        aria-label={visible ? "Hide password" : "Show password"}
        className="absolute inset-y-0 right-0 flex w-11 items-center rounded-r-lg justify-center text-text-tertiary transition-colors hover:text-text-secondary"
      >
        {visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
      </button>
    </div>
  );
}

export function TextArea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={`${FIELD_BASE} ui-textarea ${props.className ?? ""}`} />;
}

export function ErrorText({ children, id }: { children?: string; id?: string }) {
  if (!children) return null;
  return <p id={id} role="alert" className="mt-1 text-sm text-danger-600">{children}</p>;
}
