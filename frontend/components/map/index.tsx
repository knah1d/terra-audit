"use client";

import dynamic from "next/dynamic";

// ssr: false is required — Leaflet touches `window` at module load time,
// which crashes during server rendering otherwise.
export const DrawMap = dynamic(() => import("./DrawMap"), {
  ssr: false,
  loading: () => <div className="h-[400px] w-full animate-pulse rounded-md bg-gray-100" />,
});

export const GeometryPreviewMap = dynamic(() => import("./GeometryPreviewMap"), {
  ssr: false,
  loading: () => <div className="h-[300px] w-full animate-pulse rounded-md bg-gray-100" />,
});
