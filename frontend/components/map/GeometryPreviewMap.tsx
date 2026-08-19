"use client";

import L from "leaflet";
import { useEffect } from "react";
import { GeoJSON as GeoJSONLayer, MapContainer, TileLayer, useMap } from "react-leaflet";

function FitBounds({ feature }: { feature: GeoJSON.Feature }) {
  const map = useMap();
  useEffect(() => {
    const layer = L.geoJSON(feature);
    const bounds = layer.getBounds();
    if (bounds.isValid()) map.fitBounds(bounds, { padding: [20, 20] });
  }, [feature, map]);
  return null;
}

/** Read-only — no draw control. Used for upload/paste geometry preview and
 * for displaying an already-saved field's boundary. */
export default function GeometryPreviewMap({ feature }: { feature: GeoJSON.Feature }) {
  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <MapContainer
        center={[23.685, 90.3563]}
        zoom={7}
        style={{ height: "300px", width: "100%" }}
        scrollWheelZoom={false}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <GeoJSONLayer data={feature} style={{ color: "#4f46e5", weight: 2, fillOpacity: 0.12 }} />
        <FitBounds feature={feature} />
      </MapContainer>
    </div>
  );
}
