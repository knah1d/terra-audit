import type { PointerEvent } from "react";

/**
 * Drives the `.liquid-hover` CSS primitive's moving reflection
 * (app/globals.css) — writes the pointer position straight onto the
 * element's own style as CSS custom properties, so only compositor-level
 * paint (a radial-gradient position) updates on every pointer move. No
 * React state, no re-render, no listener outside the element's own
 * pointer events.
 *
 * Wire to both onPointerEnter and onPointerMove: onPointerMove alone would
 * leave --mouse-x/--mouse-y stale from wherever the pointer last left this
 * element, so the reflection can jump on re-entry before the first move
 * event fires.
 */
export function trackLiquidPointer<T extends HTMLElement>(event: PointerEvent<T>) {
  if (event.pointerType !== "mouse" && event.pointerType !== "pen") return;
  const element = event.currentTarget;
  const bounds = element.getBoundingClientRect();
  element.style.setProperty("--mouse-x", `${event.clientX - bounds.left}px`);
  element.style.setProperty("--mouse-y", `${event.clientY - bounds.top}px`);
}

/** Recenters the reflection — called on pointer leave so the next entry
 * (from an unpredictable edge) starts from the middle rather than
 * snapping from a stale position while the glass fades in. */
export function resetLiquidPointer<T extends HTMLElement>(event: PointerEvent<T>) {
  const element = event.currentTarget;
  element.style.setProperty("--mouse-x", "50%");
  element.style.setProperty("--mouse-y", "50%");
}
