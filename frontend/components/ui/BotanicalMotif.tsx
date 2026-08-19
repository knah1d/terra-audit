/**
 * Abstract botanical line-art — soft leaf/rice-panicle silhouettes,
 * single pine stroke, heavily blurred and low-opacity. Hand-authored
 * inline SVG (no image fetch, no icon-CDN dependency), positioned
 * absolutely behind foreground content.
 *
 * Deliberately bounded to two places in the app (auth pages, EmptyState)
 * — see .claude/plans/misty-growing-yao.md. Never used inside a data
 * screen (tables, forms, the ledger); that boundary is what keeps this
 * "tasteful atmosphere" rather than the eco-cliché decoration the
 * original design brief explicitly ruled out.
 */
export function BotanicalMotif({
  size = "lg",
  className = "",
}: {
  /** lg = auth-page backdrop; sm = EmptyState accent. */
  size?: "sm" | "lg";
  className?: string;
}) {
  const dimension = size === "lg" ? 560 : 220;
  const blur = size === "lg" ? "blur-[48px]" : "blur-[28px]";
  const opacity = size === "lg" ? "opacity-[0.10]" : "opacity-[0.14]";

  return (
    <svg
      width={dimension}
      height={dimension}
      viewBox="0 0 200 200"
      fill="none"
      aria-hidden
      className={`pointer-events-none select-none ${blur} ${opacity} ${className}`}
    >
      {/* Three overlapping rice-leaf/panicle silhouettes — abstract, not
       * literal, so it reads as atmosphere rather than clip-art at the
       * blur/opacity levels this is actually rendered at. */}
      <path
        d="M100 190 C60 160 40 110 55 60 C65 25 95 8 100 10 C90 40 88 90 100 130 C108 155 108 175 100 190Z"
        fill="var(--pine-600)"
      />
      <path
        d="M100 190 C140 155 158 105 145 55 C133 20 105 6 100 8 C112 38 116 88 105 128 C98 154 96 175 100 190Z"
        fill="var(--pine-500)"
      />
      <path
        d="M40 175 C55 130 90 100 95 105 C85 130 65 160 40 175Z"
        fill="var(--pine-400)"
      />
      <path
        d="M160 175 C145 130 110 100 105 105 C115 130 135 160 160 175Z"
        fill="var(--pine-400)"
      />
    </svg>
  );
}
