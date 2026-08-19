import type { LucideIcon } from "lucide-react";

const SIZE_CLASSES = {
  sm: { tile: "size-7 rounded-md", icon: "size-3.5" },
  md: { tile: "size-9 rounded-lg", icon: "size-4" },
  lg: { tile: "size-10 rounded-xl", icon: "size-5" },
};

/**
 * Icon inside a rounded, pine-tinted tile — the practical, low-risk
 * equivalent of a "duotone" icon treatment. lucide-react ships single-tone
 * stroke icons (no dual-path rendering available without hand-drawn icon
 * variants); a tinted tile behind a flat icon is what actually produces
 * the "designed, not default" read in reference apps (Linear/Notion/
 * Vercel all use this), and formalizes a pattern that already existed ad
 * hoc in a couple of places before this pass.
 */
export function IconTile({
  icon: Icon,
  size = "md",
  tone = "brand",
}: {
  icon: LucideIcon;
  size?: "sm" | "md" | "lg";
  tone?: "brand" | "neutral";
}) {
  const { tile, icon } = SIZE_CLASSES[size];
  const toneClasses =
    tone === "brand" ? "bg-brand-50 text-brand-700" : "bg-surface-muted text-text-tertiary";
  return (
    <div className={`flex shrink-0 items-center justify-center ${tile} ${toneClasses}`}>
      <Icon className={icon} />
    </div>
  );
}
