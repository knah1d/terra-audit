"use client";

import dynamic from "next/dynamic";

// ssr: false because the control's active state depends on next-themes'
// client-resolved theme — rendering it on the server would either mismatch
// during hydration or need a setState-in-effect mounted guard (which the
// react-hooks lint rules correctly reject). Same pattern as
// components/map/index.tsx. The fallback reserves exact size so the
// sidebar footer doesn't shift when it swaps in.
export const ThemeToggle = dynamic(() => import("./ThemeToggleControl"), {
  ssr: false,
  loading: () => <div className="h-8 w-[92px] rounded-md bg-surface-muted" />,
});
