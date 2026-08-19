/**
 * Floating glass action bar — the "floating toolbar" component from the
 * Liquid Glass brief. Distinct from PageHeader (plain title+subtitle):
 * this is for a page's primary action row, rendered as its own floating
 * chrome surface rather than inline page content.
 */
export function Toolbar({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`glass-chrome sticky top-4 z-chrome mb-6 flex items-center gap-2 rounded-2xl px-3 py-2 ${className}`}
    >
      {children}
    </div>
  );
}
