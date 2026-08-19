/**
 * The layer behind the glass.
 *
 * This exists for one reason: `backdrop-filter` has nothing to do over a
 * flat background — a translucent panel over flat white is just a white
 * panel, which is the single most common reason CSS glassmorphism looks
 * cheap. These two fixed layers give the blur something to refract:
 * very-low-opacity pine-tinted radial gradients, plus a faint grain that
 * removes the "digital plastic" flatness.
 *
 * Both are deliberately near-imperceptible on their own — you should
 * notice the glass working, not notice the background.
 */
export function AppBackground() {
  return (
    <>
      <div className="app-ambient" aria-hidden />
      <div className="app-grain" aria-hidden />
    </>
  );
}
