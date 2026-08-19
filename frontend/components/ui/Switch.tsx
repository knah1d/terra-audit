"use client";

/**
 * iOS-style toggle switch — replaces the plain <input type="checkbox">
 * boolean fields (practice-data page). Track + spring-animated thumb via
 * the shared --curve-out easing, brand-600 track when on.
 */
export function Switch({
  checked,
  onChange,
  label,
  disabled = false,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label?: string;
  disabled?: boolean;
}) {
  return (
    <label
      className={`inline-flex items-center gap-2.5 ${disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer"}`}
    >
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-6 w-10 shrink-0 items-center rounded-full transition-colors duration-[var(--dur-fast)] ease-[var(--curve-out)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600 ${
          checked ? "bg-brand-600" : "bg-surface-muted border border-border"
        }`}
      >
        <span
          className={`inline-block size-[18px] rounded-full bg-white shadow-sm transition-transform duration-[var(--dur-base)] ease-[var(--curve-out)] ${
            checked ? "translate-x-[19px]" : "translate-x-[3px]"
          }`}
        />
      </button>
      {label && <span className="text-sm text-text-secondary">{label}</span>}
    </label>
  );
}
