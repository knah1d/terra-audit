"use client";

import { Check, ChevronDown } from "lucide-react";
import {
  Children, Fragment, forwardRef, isValidElement, useCallback, useEffect,
  useId, useLayoutEffect, useRef, useState,
  type CSSProperties, type ReactNode, type SelectHTMLAttributes,
} from "react";
import { createPortal } from "react-dom";

type Option = { value: string; label: string; disabled: boolean; hidden: boolean; group?: string };

function textOf(node: ReactNode): string {
  return Children.toArray(node).map((child): string =>
    isValidElement<{ children?: ReactNode }>(child) ? textOf(child.props.children) : String(child),
  ).join("");
}

function optionsOf(children: ReactNode, group?: string, disabled = false): Option[] {
  return Children.toArray(children).flatMap((child): Option[] => {
    if (!isValidElement<{ children?: ReactNode; value?: string | number; label?: string; disabled?: boolean; hidden?: boolean }>(child)) return [];
    if (child.type === Fragment) return optionsOf(child.props.children, group, disabled);
    if (child.type === "optgroup") return optionsOf(child.props.children, child.props.label, disabled || !!child.props.disabled);
    if (child.type !== "option") return [];
    const label = child.props.label ?? textOf(child.props.children);
    return [{
      value: String(child.props.value ?? label), label,
      disabled: disabled || !!child.props.disabled, hidden: !!child.props.hidden, group,
    }];
  });
}

const TYPEAHEAD_MS = 600;

/**
 * Select-only combobox (WAI-ARIA APG pattern) over a visually hidden native
 * <select>. The native element stays the source of truth for FormData,
 * required validation, form reset and React Hook Form refs; only the custom
 * trigger and listbox are exposed to assistive tech.
 */
export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(function Select(
  { children, className = "", style, onChange, onBlur, onFocus, onInvalid, ...props }, forwardedRef,
) {
  const uid = useId();
  const native = useRef<HTMLSelectElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const options = optionsOf(children);
  const [nativeValue, setNativeValue] = useState(() => {
    if (props.defaultValue !== undefined) return String(props.defaultValue);
    return options.find((o) => !o.disabled && !o.hidden)?.value ?? options[0]?.value ?? "";
  });
  const value = props.value === undefined ? nativeValue : String(props.value);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [invalid, setInvalid] = useState(false);
  const invalidRef = useRef(false);
  const [label, setLabel] = useState("");
  const [position, setPosition] = useState<CSSProperties>({ visibility: "hidden" });
  const search = useRef({ text: "", time: 0 });
  const enabled = options.map((o, i) => (!o.disabled && !o.hidden ? i : -1)).filter((i) => i >= 0);
  const selected = options.findIndex((o) => o.value === value);
  const listId = `${uid}-list`;
  const optionId = (i: number) => `${uid}-option-${i}`;

  const markInvalid = (next: boolean) => { invalidRef.current = next; setInvalid(next); };

  const assignRef = useCallback((node: HTMLSelectElement | null) => {
    native.current = node;
    if (typeof forwardedRef === "function") forwardedRef(node);
    else if (forwardedRef) forwardedRef.current = node;
  }, [forwardedRef]);

  // Form libraries (RHF reset/setValue) assign .value without firing change.
  // Intercept the instance property so the trigger label follows the DOM.
  useLayoutEffect(() => {
    const node = native.current;
    if (!node) return;
    let alive = true;
    const sync = () => {
      if (!alive) return;
      setNativeValue(node.value);
      if (invalidRef.current && node.validity.valid) markInvalid(false);
    };
    const proto = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value")!;
    Object.defineProperty(node, "value", {
      configurable: true,
      get() { return proto.get!.call(this); },
      set(next: string) { proto.set!.call(this, next); queueMicrotask(sync); },
    });
    // The reset event fires before the form restores defaults; read after.
    const reset = () => { markInvalid(false); setOpen(false); setTimeout(sync, 0); };
    const observer = new MutationObserver(sync);
    observer.observe(node, { childList: true, subtree: true, attributes: true });
    const form = node.form;
    form?.addEventListener("reset", reset);
    sync();
    return () => {
      alive = false;
      observer.disconnect();
      form?.removeEventListener("reset", reset);
      Reflect.deleteProperty(node, "value");
    };
  }, []);

  // Derive an accessible name from an adjacent/wrapping <label> when the
  // consumer does not pass aria-label/aria-labelledby.
  useLayoutEffect(() => {
    const node = native.current;
    if (!node) return;
    const wrapper = node.parentElement;
    const associated = node.labels?.[0] ?? wrapper?.previousElementSibling;
    if (associated?.tagName !== "LABEL") return;
    const copy = associated.cloneNode(true) as HTMLElement;
    copy.querySelectorAll("select, button, input, textarea, svg, [role=listbox]").forEach((el) => el.remove());
    setLabel(copy.textContent?.trim() ?? "");
  });

  function choose(index: number) {
    const node = native.current;
    const option = options[index];
    if (!node || !option || option.disabled || option.hidden || node.matches(":disabled")) return;
    setOpen(false);
    if (option.value === node.value) return;
    node.value = option.value;
    setNativeValue(option.value);
    if (invalidRef.current && node.validity.valid) markInvalid(false);
    node.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function show(index?: number) {
    if (native.current?.matches(":disabled")) return;
    const start = index ?? (enabled.includes(selected) ? selected : enabled[0] ?? -1);
    setActive(start);
    setOpen(true);
  }

  useLayoutEffect(() => {
    if (!open) return;
    const popup = menu.current;
    const button = trigger.current;
    if (!popup || !button) return;
    // Top layer keeps the menu above dialog sheets and clipping ancestors.
    if (typeof popup.showPopover === "function" && !popup.matches(":popover-open")) popup.showPopover();
    const place = () => {
      const rect = button.getBoundingClientRect();
      const vv = window.visualViewport;
      const left0 = vv?.offsetLeft ?? 0;
      const top0 = vv?.offsetTop ?? 0;
      const vw = vv?.width ?? window.innerWidth;
      const vh = vv?.height ?? window.innerHeight;
      const gap = 4;
      const edge = 8;
      const below = top0 + vh - rect.bottom - gap - edge;
      const above = rect.top - top0 - gap - edge;
      const natural = popup.scrollHeight;
      const upward = below < Math.min(natural, 220) && above > below;
      const maxHeight = Math.max(44, Math.min(320, upward ? above : below));
      const width = Math.min(Math.max(rect.width, 180), vw - edge * 2);
      const height = Math.min(natural, maxHeight);
      setPosition({
        position: "fixed", margin: 0, inset: "auto", visibility: "visible", width, maxHeight,
        left: Math.max(left0 + edge, Math.min(rect.left, left0 + vw - width - edge)),
        top: upward ? Math.max(top0 + edge, rect.top - height - gap) : rect.bottom + gap,
      });
    };
    place();
    const outside = (e: PointerEvent) => {
      const target = e.target as Node;
      if (!popup.contains(target) && !button.contains(target)) setOpen(false);
    };
    const onScroll = (e: Event) => { if (e.target !== popup) place(); };
    document.addEventListener("pointerdown", outside, true);
    window.addEventListener("resize", place);
    window.addEventListener("scroll", onScroll, true);
    addViewportListener(place);
    return () => {
      document.removeEventListener("pointerdown", outside, true);
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", onScroll, true);
      removeViewportListener(place);
      if (popup.matches?.(":popover-open")) popup.hidePopover();
      setPosition({ visibility: "hidden" });
    };
  }, [open]);

  useEffect(() => {
    if (!open || active < 0) return;
    document.getElementById(optionId(active))?.scrollIntoView({ block: "nearest" });
    // optionId is derived from uid only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, open]);

  useEffect(() => { if (props.disabled) setOpen(false); }, [props.disabled]);

  // No multi-select/listbox consumers exist; keep native semantics there.
  if (props.multiple || (props.size && props.size > 1)) {
    return <select {...props} ref={forwardedRef} onChange={onChange} onBlur={onBlur} onFocus={onFocus} onInvalid={onInvalid} className={`ui-control ${className}`} style={style}>{children}</select>;
  }

  const name = props["aria-label"] ?? (label || undefined);
  const labelledBy = props["aria-labelledby"];

  return <span className={`ui-select ${className}`} style={style} data-open={open || undefined}>
    <select {...props} ref={assignRef} aria-hidden="true" tabIndex={-1} className="ui-select-native"
      onChange={(event) => { setNativeValue(event.currentTarget.value); onChange?.(event); }}
      onFocus={(event) => { trigger.current?.focus(); onFocus?.(event); }}
      onBlur={onBlur}
      onInvalid={(event) => {
        // Suppress the native bubble (it would point at a hidden element)
        // and surface the error on the visible trigger instead.
        event.preventDefault();
        markInvalid(true);
        const form = event.currentTarget.form;
        const firstInvalid = form?.querySelector(":invalid:not(form):not(fieldset)");
        if (!form || firstInvalid === event.currentTarget) trigger.current?.focus();
        onInvalid?.(event);
      }}>
      {children}
    </select>
    <button ref={trigger} type="button" role="combobox" id={props.id ? `${props.id}-trigger` : undefined}
      className="ui-control ui-select-trigger"
      disabled={props.disabled} autoFocus={props.autoFocus}
      aria-label={labelledBy ? undefined : name ?? props.name ?? "Choose an option"}
      aria-labelledby={labelledBy} aria-describedby={props["aria-describedby"]}
      aria-required={props.required || undefined}
      aria-invalid={props["aria-invalid"] ?? (invalid || undefined)}
      aria-expanded={open} aria-haspopup="listbox" aria-controls={open ? listId : undefined}
      aria-activedescendant={open && active >= 0 ? optionId(active) : undefined}
      onClick={() => (open ? setOpen(false) : show())}
      onBlur={(event) => {
        setOpen(false);
        // Mirror blur to the native element so RHF onTouched/onBlur modes work.
        const node = native.current;
        if (node) {
          const synthetic = new FocusEvent("focusout", { bubbles: true, relatedTarget: event.relatedTarget });
          node.dispatchEvent(synthetic);
        }
      }}
      onKeyDown={(event) => {
        const key = event.key;
        if (key === "Escape") {
          if (open) { event.preventDefault(); event.stopPropagation(); setOpen(false); }
          return;
        }
        if (key === "Tab") { if (open) choose(active); return; }
        if (event.altKey && (key === "ArrowDown" || key === "ArrowUp")) {
          event.preventDefault();
          if (open) { if (key === "ArrowUp") choose(active); } else show();
          return;
        }
        if (["ArrowDown", "ArrowUp", "Home", "End", "PageDown", "PageUp"].includes(key)) {
          event.preventDefault();
          if (!open) { show(key === "End" ? enabled.at(-1) : key === "Home" ? enabled[0] : undefined); return; }
          if (!enabled.length) return;
          const at = enabled.indexOf(active);
          const delta = key === "PageDown" ? 10 : key === "PageUp" ? -10 : key === "ArrowDown" ? 1 : -1;
          const next = key === "Home" ? 0 : key === "End" ? enabled.length - 1
            : Math.max(0, Math.min(enabled.length - 1, (at < 0 ? (delta > 0 ? -1 : enabled.length) : at) + delta));
          setActive(enabled[next]);
          return;
        }
        const now = Date.now();
        const typing = now - search.current.time <= TYPEAHEAD_MS && search.current.text !== "";
        if (key === "Enter" || (key === " " && !typing)) {
          event.preventDefault();
          if (open) choose(active); else show();
          return;
        }
        if (key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
          event.preventDefault();
          const query = typing ? search.current.text + key : key;
          search.current = { text: query, time: now };
          const repeated = [...query].every((c) => c === query[0]);
          const term = (repeated ? key : query).toLocaleLowerCase();
          const current = open ? active : selected;
          const start = repeated ? enabled.indexOf(current) + 1 : Math.max(0, enabled.indexOf(current));
          const ordered = [...enabled.slice(start), ...enabled.slice(0, start)];
          const match = ordered.find((i) => options[i].label.trim().toLocaleLowerCase().startsWith(term));
          if (match === undefined) return;
          if (open) setActive(match); else choose(match);
        }
      }}>
      <span className={`min-w-0 flex-1 truncate text-left ${selected < 0 || options[selected]?.hidden ? "text-text-tertiary" : ""}`}>
        {options[selected]?.label || "Choose an option"}
      </span>
      <ChevronDown aria-hidden="true" className="ui-select-chevron" />
    </button>
    {open && createPortal(
      <div ref={menu} id={listId} role="listbox" popover="manual" className="ui-select-menu" style={position}
        aria-label={labelledBy ? undefined : name ?? props.name ?? "Options"} aria-labelledby={labelledBy}
        onPointerDown={(event) => event.preventDefault()}>
        {options.map((option, index) => option.hidden ? null : <Fragment key={`${option.value}-${index}`}>
          {option.group && option.group !== options[index - 1]?.group && <div role="presentation" className="ui-select-group">{option.group}</div>}
          <div id={optionId(index)} role="option" aria-selected={value === option.value}
            aria-disabled={option.disabled || undefined}
            data-active={active === index || undefined} className="ui-select-option"
            onPointerMove={() => { if (!option.disabled && active !== index) setActive(index); }}
            onClick={() => { if (!option.disabled) choose(index); }}>
            <span className="min-w-0 flex-1 break-words">{option.label}</span>
            {value === option.value && <Check aria-hidden="true" className="size-4 shrink-0" />}
          </div>
        </Fragment>)}
        {!enabled.length && <div className="ui-select-group">No options available</div>}
      </div>,
      trigger.current?.closest("dialog") ?? document.body,
    )}
  </span>;
});

function addViewportListener(fn: () => void) {
  window.visualViewport?.addEventListener("resize", fn);
  window.visualViewport?.addEventListener("scroll", fn);
}
function removeViewportListener(fn: () => void) {
  window.visualViewport?.removeEventListener("resize", fn);
  window.visualViewport?.removeEventListener("scroll", fn);
}
