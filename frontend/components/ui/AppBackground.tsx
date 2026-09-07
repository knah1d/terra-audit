/** Fixed atmosphere provides visible depth beneath translucent panels. */
export function AppBackground() {
  return <><div className="app-ambient" aria-hidden /><div className="app-grain" aria-hidden /></>;
}
