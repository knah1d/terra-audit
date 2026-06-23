import json
import math
import xml.etree.ElementTree as ET


def compute_area_ha(geojson_feature: dict) -> float:
    """
    Shoelace formula with spherical latitude correction.
    Accepts a GeoJSON Feature with a Polygon geometry.
    Returns area in hectares, rounded to 4 decimal places.
    """
    coords = geojson_feature["geometry"]["coordinates"][0]
    lat_c = sum(c[1] for c in coords) / len(coords)
    m_per_lat = 111_320.0
    m_per_lon = 111_320.0 * math.cos(math.radians(lat_c))
    area_m2 = 0.0
    n = len(coords)
    for i in range(n - 1):
        x1, y1 = coords[i][0] * m_per_lon,   coords[i][1] * m_per_lat
        x2, y2 = coords[i+1][0] * m_per_lon, coords[i+1][1] * m_per_lat
        area_m2 += x1 * y2 - x2 * y1
    return round(abs(area_m2) / 2 / 10_000, 4)


def parse_geojson_upload(content: str):
    """
    Parse a GeoJSON string (FeatureCollection, Feature, Polygon, or MultiPolygon).
    Returns (feature_dict, None) on success or (None, error_message) on failure.
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON: {e}"
    t = data.get("type")
    if t == "FeatureCollection":
        features = data.get("features", [])
        if not features:
            return None, "FeatureCollection contains no features."
        feat = features[0]
    elif t == "Feature":
        feat = data
    elif t in ("Polygon", "MultiPolygon"):
        feat = {"type": "Feature", "properties": {}, "geometry": data}
    else:
        return None, f"Unsupported GeoJSON type: '{t}'"
    geom_type = feat.get("geometry", {}).get("type", "")
    if geom_type not in ("Polygon", "MultiPolygon"):
        return None, f"Geometry must be Polygon or MultiPolygon, got '{geom_type}'."
    return feat, None


def parse_kml_upload(content: str):
    """
    Extract the first polygon from a KML string.
    Returns (feature_dict, None) on success or (None, error_message) on failure.
    """
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        return None, f"Invalid KML: {e}"
    kml_ns = "http://www.opengis.net/kml/2.2"
    tags = [f"{{{kml_ns}}}coordinates", "coordinates"]
    for tag in tags:
        for elem in root.iter(tag):
            text = (elem.text or "").strip()
            coords = []
            for point in text.split():
                parts = point.split(",")
                if len(parts) >= 2:
                    try:
                        coords.append([float(parts[0]), float(parts[1])])
                    except ValueError:
                        continue
            if len(coords) >= 3:
                if coords[0] != coords[-1]:
                    coords.append(coords[0])
                return {
                    "type": "Feature", "properties": {},
                    "geometry": {"type": "Polygon", "coordinates": [coords]},
                }, None
    return None, "No valid polygon coordinates found in KML."


def parse_coordinate_text(text: str):
    """
    Parse newline-separated 'lat, lon' pairs into a GeoJSON Feature.
    Accepts comma or space separators. Requires at least 3 valid points.
    Returns (feature_dict, None) on success or (None, error_message) on failure.
    """
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    coords, bad = [], []
    for line in lines:
        parts = line.replace(",", " ").replace("\t", " ").split()
        if len(parts) < 2:
            continue
        try:
            lat, lon = float(parts[0]), float(parts[1])
        except ValueError:
            bad.append(line)
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            bad.append(f"{line}  <- out of range")
            continue
        coords.append([lon, lat])
    if len(coords) < 3:
        detail = f" Unparseable lines: {bad}" if bad else ""
        return None, f"Need at least 3 valid points, got {len(coords)}.{detail}"
    if coords[0] != coords[-1]:
        coords.append(coords[0])
    return {
        "type": "Feature", "properties": {},
        "geometry": {"type": "Polygon", "coordinates": [coords]},
    }, None
