"use client";

import L from "leaflet";
import "leaflet-draw";
// The plugin's own stylesheet — without it the draw toolbar has no icon
// sprites/sizing and its buttons fall back to raw, overlapping title
// text (a real bug: only `leaflet/dist/leaflet.css`, leaflet-draw's own
// base, was ever imported — not leaflet-draw's). Scoped to this
// component (the only leaflet-draw consumer) rather than the root
// layout, matching where the plugin's JS import already lives.
import "leaflet-draw/dist/leaflet.draw.css";
import { useEffect, useRef } from "react";
import { MapContainer, TileLayer, useMap } from "react-leaflet";

const DEFAULT_CENTER: [number, number] = [23.685, 90.3563]; // Bangladesh centroid
const DEFAULT_ZOOM = 7;

function DrawControl({ onDrawn }: { onDrawn: (feature: GeoJSON.Feature) => void }) {
  const map = useMap();
  const drawnItemsRef = useRef<L.FeatureGroup | null>(null);

  useEffect(() => {
    const drawnItems = new L.FeatureGroup();
    drawnItemsRef.current = drawnItems;
    map.addLayer(drawnItems);

    // Only polygon + rectangle — matches app.py's draw_options restriction.
    const drawControl = new L.Control.Draw({
      draw: {
        polygon: { allowIntersection: false, showArea: true },
        rectangle: {},
        polyline: false,
        circle: false,
        circlemarker: false,
        marker: false,
      },
      edit: { featureGroup: drawnItems, remove: true },
    });
    map.addControl(drawControl);

    function handleCreated(e: L.LeafletEvent) {
      const event = e as unknown as { layer: L.Layer };
      drawnItems.clearLayers(); // one field boundary at a time
      drawnItems.addLayer(event.layer);
      const geoLayer = event.layer as unknown as { toGeoJSON: () => GeoJSON.Feature };
      onDrawn(geoLayer.toGeoJSON());
    }

    map.on(L.Draw.Event.CREATED, handleCreated);
    return () => {
      map.off(L.Draw.Event.CREATED, handleCreated);
      map.removeControl(drawControl);
      map.removeLayer(drawnItems);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map]);

  return null;
}

export default function DrawMap({ onDrawn }: { onDrawn: (feature: GeoJSON.Feature) => void }) {
  return (
    <MapContainer
      center={DEFAULT_CENTER}
      zoom={DEFAULT_ZOOM}
      style={{ height: "400px", width: "100%" }}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <DrawControl onDrawn={onDrawn} />
    </MapContainer>
  );
}
