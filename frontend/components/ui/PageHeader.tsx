/** Title + optional subtitle + trailing actions — replaces the repeated
 * <h1 className="text-2xl font-semibold">...</h1> pattern across pages.
 * Large-title sizing (text-3xl/4xl) and generous bottom margin match
 * Apple's own large-title header pattern (Settings, Health, Wallet) —
 * bumped up from a standard-dashboard text-2xl in the Liquid Glass pass. */
export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <div className="mb-8 flex items-start justify-between gap-4 md:mb-10">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight text-text-primary md:text-4xl">
          {title}
        </h1>
        {subtitle && <p className="mt-2 text-sm text-text-secondary">{subtitle}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}
