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
    <div className="enter mb-8 flex flex-col items-start justify-between gap-4 sm:flex-row">
      <div className="min-w-0">
        <h1 className="ui-page-title">
          {title}
        </h1>
        {subtitle && <p className="ui-secondary mt-2">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2 sm:shrink-0">{actions}</div>}
    </div>
  );
}
