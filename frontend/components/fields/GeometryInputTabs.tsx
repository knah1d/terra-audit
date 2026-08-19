"use client";

import { ClipboardList, PenLine, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { DrawMap } from "@/components/map";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { FieldLabel, TextArea } from "@/components/ui/Field";
import { Tabs } from "@/components/ui/Tabs";
import { useParseCoordinates, useParseGeojson, useParseKml } from "@/hooks/use-geometry";

type InputMode = "draw" | "upload" | "paste";

const MODE_OPTIONS = [
  { value: "draw" as const, label: "Draw on Map", icon: PenLine },
  { value: "upload" as const, label: "Upload GeoJSON/KML", icon: Upload },
  { value: "paste" as const, label: "Paste Coordinates", icon: ClipboardList },
];

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
      <div className="mb-4">
        <Tabs options={MODE_OPTIONS} value={mode} onChange={setMode} />
      </div>

      {mode === "draw" && (
        <div className="overflow-hidden rounded-lg border border-border">
          <DrawMap onDrawn={onGeometry} />
        </div>
      )}

      {mode === "upload" && (
        <div>
          <FieldLabel>Upload a .geojson, .json, or .kml file</FieldLabel>
          <input
            ref={fileInputRef}
            type="file"
            accept=".geojson,.json,.kml"
            onChange={handleFileChange}
            className="block w-full text-sm text-text-secondary"
          />
        </div>
      )}

      {mode === "paste" && (
        <div>
          <FieldLabel>Paste GPS coordinates (one &quot;lat, lon&quot; pair per line, ≥3 required)</FieldLabel>
          <TextArea
            value={pasteText}
            onChange={(e) => setPasteText(e.target.value)}
            rows={6}
            placeholder={"23.70, 90.40\n23.71, 90.40\n23.71, 90.41\n23.70, 90.41"}
          />
          <Button type="button" onClick={handlePasteSubmit} loading={parseCoordinates.isPending} className="mt-2" size="sm">
            Parse coordinates
          </Button>
        </div>
      )}

      {activeMutation?.data?.error && (
        <Alert tone="danger" className="mt-3">
          {activeMutation.data.error}
        </Alert>
      )}
      {activeMutation?.isError && (
        <Alert tone="danger" className="mt-3">
          {(activeMutation.error as Error).message}
        </Alert>
      )}
    </div>
  );
}
