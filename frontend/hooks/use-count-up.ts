"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Animates a number ticking from its previous value to a new one over
 * ~500ms — used on the Final Issuance stat so a fresh calculation draws
 * the eye instead of just snapping to the new figure. Plain
 * requestAnimationFrame, no animation library: matches this app's
 * established "CSS/JS-native over a new dependency" pattern.
 *
 * Respects prefers-reduced-motion by rendering the target directly,
 * skipping the animated state entirely. reduceMotion is read once via a
 * lazy useState initializer (safe during render, unlike a ref read —
 * refs may only be read in effects/handlers) rather than a ref.
 */
export function useCountUp(target: number, durationMs = 500): number {
  const [reduceMotion] = useState(
    () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  const [value, setValue] = useState(target);
  const fromRef = useRef(target);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    if (reduceMotion || !Number.isFinite(target)) {
      fromRef.current = target;
      return;
    }

    const from = fromRef.current;
    if (from === target) return;

    const start = performance.now();
    function tick(now: number) {
      const elapsed = now - start;
      const t = Math.min(1, elapsed / durationMs);
      // ease-out cubic — a quick start that settles, matching the app's
      // --curve-out spring-like feel without needing the CSS var here.
      const eased = 1 - Math.pow(1 - t, 3);
      setValue(from + (target - from) * eased);
      if (t < 1) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        fromRef.current = target;
      }
    }
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
  }, [target, durationMs, reduceMotion]);

  return reduceMotion || !Number.isFinite(target) ? target : value;
}
