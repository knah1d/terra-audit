/** Reveal an active navigation item without scrolling the page vertically. */
export function revealNavigationItem(viewport: HTMLElement | null, item: HTMLElement | null) {
  if (!viewport || !item) return;
  const bounds = viewport.getBoundingClientRect();
  const target = item.getBoundingClientRect();
  if (target.left < bounds.left) viewport.scrollLeft -= bounds.left - target.left + 8;
  else if (target.right > bounds.right) viewport.scrollLeft += target.right - bounds.right + 8;
}
