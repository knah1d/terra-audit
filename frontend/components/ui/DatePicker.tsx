"use client";

import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";
import { forwardRef, useCallback, useId, useLayoutEffect, useRef, useState, type CSSProperties, type InputHTMLAttributes } from "react";
import { createPortal } from "react-dom";

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const pad = (n: number) => String(n).padStart(2, "0");
// Local calendar arithmetic only: a date is never converted through UTC.
function dateAt(year: number, month: number, day: number) {
  const date = new Date(0);
  date.setFullYear(year, month, day);
  date.setHours(12, 0, 0, 0);
  return date;
}
function iso(date: Date) { return `${String(date.getFullYear()).padStart(4, "0")}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`; }
function fromISO(value: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  return match ? dateAt(Number(match[1]), Number(match[2]) - 1, Number(match[3])) : null;
}
function display(value: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})(?:T(.*))?$/.exec(value);
  return match ? `${match[3]}-${match[2]}-${match[1]}${match[4] ? ` ${match[4]}` : ""}` : "";
}
function parse(text: string, withTime: boolean): string | null {
  if (!text.trim()) return "";
  const match = /^(\d{2})-(\d{2})-(\d{4})(?:\s+(\d{2}):(\d{2})(?::(\d{2}))?)?$/.exec(text.trim());
  if (!match || (!!match[4] !== withTime)) return null;
  const [, day, month, year, hour, minute, second] = match;
  const date = dateAt(Number(year), Number(month) - 1, Number(day));
  if (Number(year) < 1 || date.getFullYear() !== Number(year) || date.getMonth() !== Number(month) - 1 || date.getDate() !== Number(day)) return null;
  if (withTime && (Number(hour) > 23 || Number(minute) > 59 || Number(second ?? 0) > 59)) return null;
  return `${year}-${month}-${day}${withTime ? `T${hour}:${minute}${second ? `:${second}` : ""}` : ""}`;
}

/** Visible DD-MM-YYYY editor; native date input retains ISO FormData,
 * min/max/step validation, real React change events and form-library refs. */
export const DatePicker = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function DatePicker(
  { className = "", style, value, defaultValue, onChange, onBlur, onFocus, onInvalid, placeholder, ...props }, forwardedRef,
) {
  const withTime = props.type === "datetime-local";
  const format = withTime ? "DD-MM-YYYY HH:mm" : "DD-MM-YYYY";
  const uid = useId();
  const native = useRef<HTMLInputElement>(null);
  const editor = useRef<HTMLInputElement>(null);
  const wrapper = useRef<HTMLSpanElement>(null);
  const popup = useRef<HTMLDivElement>(null);
  const initial = String(value ?? defaultValue ?? "");
  const [text, setText] = useState(() => display(initial));
  const [selected, setSelected] = useState(initial);
  const [error, setError] = useState("");
  const [label, setLabel] = useState("");
  const [open, setOpen] = useState(false);
  const [month, setMonth] = useState(() => fromISO(initial) ?? new Date());
  const [active, setActive] = useState(() => iso(fromISO(initial) ?? new Date()));
  const [position, setPosition] = useState<CSSProperties>({ visibility: "hidden" });
  const committing = useRef(false);
  const controlledValue = useRef(value);
  controlledValue.current = value;
  const hintId = `${uid}-hint`;
  const calendarId = `${uid}-calendar`;

  const assignRef = useCallback((node: HTMLInputElement | null) => {
    native.current = node;
    if (typeof forwardedRef === "function") forwardedRef(node);
    else if (forwardedRef) forwardedRef.current = node;
  }, [forwardedRef]);

  useLayoutEffect(() => {
    const node = native.current;
    if (!node) return;
    const descriptor = Object.getOwnPropertyDescriptor(node, "value");
    const proto = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!;
    let alive = true;
    const sync = () => {
      if (!alive) return;
      node.setCustomValidity("");
      setText(display(node.value)); setSelected(node.value); setError("");
    };
    // RHF setValue/reset can assign directly without a change event.
    Object.defineProperty(node, "value", {
      configurable: true,
      get() { return (descriptor?.get ?? proto.get)!.call(this); },
      set(next: string) {
        (descriptor?.set ?? proto.set)!.call(this, next);
        if (!committing.current) queueMicrotask(sync);
      },
    });
    const reset = () => {
      setOpen(false);
      setTimeout(() => {
        if (!alive) return;
        if (controlledValue.current !== undefined) proto.set!.call(node, String(controlledValue.current));
        sync();
      }, 0);
    };
    const form = node.form;
    form?.addEventListener("reset", reset);
    return () => {
      alive = false; form?.removeEventListener("reset", reset);
      if (descriptor) Object.defineProperty(node, "value", descriptor);
      else Reflect.deleteProperty(node, "value");
    };
  }, []);

  useLayoutEffect(() => {
    if (value === undefined || !native.current) return;
    const next = String(value);
    if (native.current.value !== next) {
      native.current.value = next;
    }
  }, [value]);

  useLayoutEffect(() => {
    const node = native.current;
    const associated = node?.labels?.[0] ?? wrapper.current?.previousElementSibling;
    if (associated?.tagName !== "LABEL") return;
    const copy = associated.cloneNode(true) as HTMLElement;
    copy.querySelectorAll(".ui-date, input, button, svg").forEach(el => el.remove());
    setLabel(copy.textContent?.trim() ?? "");
  });

  function commit(next: string, malformed = "") {
    const node = native.current;
    if (!node || node.matches(":disabled") || props.readOnly) return;
    node.setCustomValidity(malformed);
    setSelected(next);
    // Bypass React's value tracker so the bubbling input event invokes the
    // existing onChange with an actual input whose value is ISO, not display text.
    committing.current = true;
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(node, next);
    node.dispatchEvent(new Event("input", { bubbles: true }));
    node.dispatchEvent(new Event("change", { bubbles: true }));
    committing.current = false;
    setError(malformed || (node.validity.valid ? "" : node.validationMessage));
  }
  function close() { setOpen(false); editor.current?.focus(); }
  function show() {
    if (native.current?.matches(":disabled") || props.readOnly) return;
    const date = fromISO(selected) ?? new Date();
    setMonth(date); setActive(iso(date)); setOpen(true);
  }
  function choose(date: Date) {
    const parsed = parse(text, withTime);
    const time = (parsed || selected).split("T")[1] || "00:00";
    const next = `${iso(date)}${withTime ? `T${time}` : ""}`;
    setText(display(next)); commit(next); close();
  }
  const dateMin = props.min ? String(props.min).slice(0, 10) : "";
  const dateMax = props.max ? String(props.max).slice(0, 10) : "";
  const unavailable = (day: string) => day < "0001-01-01" || day > "9999-12-31" || (!!dateMin && day < dateMin) || (!!dateMax && day > dateMax);

  useLayoutEffect(() => {
    if (!open) return;
    const menu = popup.current;
    const anchor = wrapper.current;
    if (!menu || !anchor) return;
    if (typeof menu.showPopover === "function" && !menu.matches(":popover-open")) menu.showPopover();
    const place = () => {
      const rect = anchor.getBoundingClientRect();
      const vv = window.visualViewport;
      const left = vv?.offsetLeft ?? 0, top = vv?.offsetTop ?? 0;
      const width = vv?.width ?? window.innerWidth, height = vv?.height ?? window.innerHeight;
      const popupWidth = Math.min(336, width - 16);
      const popupHeight = Math.min(menu.scrollHeight, height - 16);
      const below = rect.bottom + 6;
      setPosition({ position: "fixed", margin: 0, inset: "auto", visibility: "visible", width: popupWidth, maxHeight: height - 16,
        left: Math.max(left + 8, Math.min(rect.left, left + width - popupWidth - 8)),
        top: Math.max(top + 8, Math.min(below + popupHeight > top + height - 8 ? rect.top - popupHeight - 6 : below, top + height - popupHeight - 8)) });
    };
    const outside = (event: PointerEvent) => {
      if (!menu.contains(event.target as Node) && !anchor.contains(event.target as Node)) setOpen(false);
    };
    place();
    document.addEventListener("pointerdown", outside, true);
    window.addEventListener("resize", place); window.addEventListener("scroll", place, true);
    window.visualViewport?.addEventListener("resize", place); window.visualViewport?.addEventListener("scroll", place);
    return () => {
      document.removeEventListener("pointerdown", outside, true);
      window.removeEventListener("resize", place); window.removeEventListener("scroll", place, true);
      window.visualViewport?.removeEventListener("resize", place); window.visualViewport?.removeEventListener("scroll", place);
      if (menu.matches(":popover-open")) menu.hidePopover();
    };
  }, [open]);

  useLayoutEffect(() => {
    if (open) popup.current?.querySelector<HTMLButtonElement>(`[data-day="${active}"]`)?.focus({ preventScroll: true });
  }, [open, active]);
  useLayoutEffect(() => { if (props.disabled || props.readOnly) setOpen(false); }, [props.disabled, props.readOnly]);

  function moveMonth(delta: number) {
    const date = dateAt(month.getFullYear(), month.getMonth() + delta, 1);
    if (date.getFullYear() < 1 || date.getFullYear() > 9999) return;
    setMonth(date); setActive(iso(date));
  }
  const first = dateAt(month.getFullYear(), month.getMonth(), 1);
  const offset = (first.getDay() + 6) % 7;
  const days = Array.from({ length: 42 }, (_, i) => dateAt(month.getFullYear(), month.getMonth(), i - offset + 1));
  const name = props["aria-label"] ?? (label || props.name || "Date");
  const describedBy = [props["aria-describedby"], hintId].filter(Boolean).join(" ");

  return <span ref={wrapper} className={`ui-date ${className}`} style={style}>
    <input {...props} ref={assignRef} id={props.id ? `${props.id}-native` : undefined} defaultValue={defaultValue ?? value}
      className="ui-date-native" tabIndex={-1} aria-hidden="true" autoFocus={false}
      onChange={event => { setSelected(event.currentTarget.value); if (!committing.current) setText(display(event.currentTarget.value)); onChange?.(event); }} onBlur={onBlur}
      onFocus={event => { editor.current?.focus(); onFocus?.(event); }}
      onInvalid={event => {
        event.preventDefault(); setError(event.currentTarget.validationMessage);
        const firstInvalid = event.currentTarget.form?.querySelector(":invalid:not(form):not(fieldset)");
        if (!firstInvalid || firstInvalid === event.currentTarget) editor.current?.focus();
        onInvalid?.(event);
      }} />
    <input ref={editor} id={props.id} type="text" className="ui-control ui-date-editor" value={text}
      placeholder={placeholder ?? format} disabled={props.disabled} readOnly={props.readOnly} autoFocus={props.autoFocus}
      autoComplete="off" spellCheck={false} aria-label={props["aria-labelledby"] ? undefined : name} aria-labelledby={props["aria-labelledby"]}
      aria-required={props.required || undefined} aria-invalid={props["aria-invalid"] ?? (!!error || undefined)} aria-describedby={describedBy}
      onChange={event => {
        const next = event.currentTarget.value;
        setText(next);
        const parsed = parse(next, withTime);
        commit(parsed ?? "", parsed === null ? `Enter a valid date in ${format} format.` : "");
      }}
      onFocus={() => native.current?.dispatchEvent(new FocusEvent("focusin", { bubbles: true }))}
      onBlur={event => {
        native.current?.dispatchEvent(new FocusEvent("focusout", { bubbles: true, relatedTarget: event.relatedTarget }));
        if (native.current && !native.current.validity.valid) setError(native.current.validationMessage);
      }}
      onKeyDown={event => {
        if (event.key === "ArrowDown" && event.altKey) { event.preventDefault(); show(); }
        if (event.key === "Escape" && open) { event.preventDefault(); event.stopPropagation(); close(); }
      }} />
    <button type="button" className="ui-date-toggle" disabled={props.disabled || props.readOnly} aria-label={`Open calendar for ${name}`}
      onKeyDown={event => { if (event.key === "Escape" && open) { event.preventDefault(); event.stopPropagation(); close(); } }}
      aria-haspopup="dialog" aria-expanded={open} aria-controls={open ? calendarId : undefined} onClick={() => open ? close() : show()}>
      <CalendarDays aria-hidden="true" className="size-4" />
    </button>
    <span id={hintId} className={error ? "ui-date-hint" : "sr-only"} aria-live="polite">{error || format}</span>
    {open && createPortal(<div ref={popup} id={calendarId} role="dialog" aria-label={`Choose ${name}`} popover="manual"
      className="ui-select-menu ui-date-menu" style={position}
      onBlur={event => { if (event.relatedTarget && !event.currentTarget.contains(event.relatedTarget as Node) && !wrapper.current?.contains(event.relatedTarget as Node)) setOpen(false); }}
      onKeyDown={event => { if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); close(); } }}>
      <div className="ui-date-heading">
        <button type="button" className="ui-date-nav" aria-label="Previous month" onClick={() => moveMonth(-1)}><ChevronLeft className="size-4" /></button>
        <span aria-live="polite" className="ui-date-month-title">{MONTHS[month.getMonth()]} {month.getFullYear()}</span>
        <button type="button" className="ui-date-nav" aria-label="Next month" onClick={() => moveMonth(1)}><ChevronRight className="size-4" /></button>
      </div>
      <div className="ui-date-jump">
        <label>Month<input type="number" aria-label="Calendar month" className="ui-control" min={1} max={12} value={month.getMonth() + 1}
          onChange={event => { const n = Number(event.target.value); if (n >= 1 && n <= 12) setMonth(dateAt(month.getFullYear(), n - 1, 1)); }} /></label>
        <label>Year<input type="number" aria-label="Calendar year" className="ui-control" min={1} max={9999} value={month.getFullYear()}
          onChange={event => { const n = Number(event.target.value); if (Number.isInteger(n) && n >= 1 && n <= 9999) setMonth(dateAt(n, month.getMonth(), 1)); }} /></label>
      </div>
      <div role="grid" aria-label={`${MONTHS[month.getMonth()]} ${month.getFullYear()}`}>
        <div role="row" className="ui-date-week">{["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"].map(day => <span role="columnheader" key={day}>{day}</span>)}</div>
        {Array.from({ length: 6 }, (_, row) => <div role="row" className="ui-date-week" key={row}>
          {days.slice(row * 7, row * 7 + 7).map(date => {
            const day = iso(date), disabled = unavailable(day);
            return <div role="gridcell" key={day} aria-selected={day === selected.slice(0, 10)}>
              <button type="button" data-day={day} className="ui-date-day" aria-disabled={disabled || undefined}
                data-muted={date.getMonth() !== month.getMonth() || undefined} data-selected={day === selected.slice(0, 10) || undefined}
                aria-current={day === iso(new Date()) ? "date" : undefined} aria-label={display(day)} tabIndex={day === active || (!days.some(d => iso(d) === active) && day === iso(first)) ? 0 : -1}
                onClick={() => { if (!disabled) choose(date); }}
                onKeyDown={event => {
                  if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End", "PageUp", "PageDown"].includes(event.key)) {
                    event.preventDefault();
                    const delta = ({ ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7, Home: -((date.getDay() + 6) % 7), End: 6 - ((date.getDay() + 6) % 7) } as Record<string, number>)[event.key];
                    const next = event.key.startsWith("Page") ? dateAt(date.getFullYear() + (event.shiftKey ? (event.key === "PageUp" ? -1 : 1) : 0), date.getMonth() + (event.shiftKey ? 0 : event.key === "PageUp" ? -1 : 1), 1)
                      : dateAt(date.getFullYear(), date.getMonth(), date.getDate() + delta);
                    if (next.getFullYear() >= 1 && next.getFullYear() <= 9999) { setActive(iso(next)); setMonth(next); }
                  }
                }}>{date.getDate()}</button>
            </div>;
          })}
        </div>)}
      </div>
      {withTime && <label className="ui-date-time-note">Time (24-hour, local)
        <input type="text" className="ui-control" placeholder="HH:mm" aria-label="Time in local timezone"
          value={text.split(/\s+/)[1] ?? ""} onChange={event => {
            const next = `${text.split(/\s+/)[0] || display(iso(fromISO(selected) ?? new Date()))} ${event.target.value}`;
            setText(next);
            const parsed = parse(next, true);
            commit(parsed ?? "", parsed === null ? `Enter a valid date in ${format} format.` : "");
          }} />
      </label>}
    </div>, wrapper.current?.closest("dialog") ?? document.body)}
  </span>;
});
