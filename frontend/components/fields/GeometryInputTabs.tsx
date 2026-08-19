"use client";

import { useRef, useState } from "react";
import { DrawMap } from "@/components/map";
import { Button } from "@/components/ui/Button";
import { FieldLabel } from "@/components/ui/Field";
import { useParseCoordinates, useParseGeojson, useParseKml } from "@/hooks/use-geometry";

type InputMode = "draw" | "upload" | "paste";

/**
 * The three geometry-input paths from app.py's sidebar, converging on one
 * callback — draw needs no server round-trip (the raw Leaflet feature is
 * already GeoJSON); upload/paste call the backend's geo_utils-wrapping
 * parse endpoints, which return either a feature or a human-readable error.
 */
export function GeometryInputTabs({ onGeometry }: { onGeometry: (feature: GeoJSON.Feature) => void }) {
  const [mode, setMode] = useState<InputMode>("draw");
  const [pasteText, setPasteText] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const parseGeojson = useParseGeojson();
  const parseKml = useParseKml();
  const parseCoordinates = useParseCoordinates();

  const activeMutation =
    mode === "upload" ? parseGeojson : mode === "paste" ? parseCoordinates : null;

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const content = await file.text();
    const isKml = file.name.toLowerCase().endsWith(".kml");
    const result = await (isKml ? parseKml.mutateAsync(content) : parseGeojson.mutateAsync(content));
    if (result.feature) onGeometry(result.feature);
  }

  async function handlePasteSubmit() {
    const result = await parseCoordinates.mutateAsync(pasteText);
    if (result.feature) onGeometry(result.feature);
  }

  return (
    <div>
      <div className="mb-4 flex gap-1 rounded-md bg-gray-100 p-1 text-sm">
        {([
          ["draw", "🖊️ Draw on Map"],
          ["upload", "📁 Upload GeoJSON/KML"],
          ["paste", "📋 Paste Coordinates"],
        ] as const).map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => setMode(value)}
            className={`flex-1 rounded-md px-3 py-1.5 font-medium transition-colors ${
              mode === value ? "bg-white shadow-sm" : "text-gray-600 hover:text-gray-900"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {mode === "draw" && <DrawMap onDrawn={onGeometry} />}

      {mode === "upload" && (
        <div>
          <FieldLabel>Upload a .geojson, .json, or .kml file</FieldLabel>
          <input
            ref={fileInputRef}
            type="file"
            accept=".geojson,.json,.kml"
            onChange={handleFileChange}
            className="block w-full text-sm text-gray-600"
          />
        </div>
      )}

      {mode === "paste" && (
        <div>
          <FieldLabel>Paste GPS coordinates (one &quot;lat, lon&quot; pair per line, ≥3 required)</FieldLabel>
          <textarea
            value={pasteText}
            onChange={(e) => setPasteText(e.target.value)}
            rows={6}
            placeholder={"23.70, 90.40\n23.71, 90.40\n23.71, 90.41\n23.70, 90.41"}
            className="w-full rounded-md border border-gray-300 px-3 py-2 font-mono text-sm focus:border-blue-500 focus:outline-none"
          />
          <Button type="button" onClick={handlePasteSubmit} disabled={parseCoordinates.isPending} className="mt-2">
            Parse Coordinates
          </Button>
        </div>
      )}

      {activeMutation?.data?.error && (
        <p className="mt-2 text-sm text-red-600">{activeMutation.data.error}</p>
      )}
      {activeMutation?.isError && (
        <p className="mt-2 text-sm text-red-600">
          {(activeMutation.error as Error).message}
        </p>
      )}
    </div>
  );
}
