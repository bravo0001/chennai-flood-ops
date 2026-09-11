import json
import osmium
from shapely.geometry import LineString, mapping

PBF_FILE = "southern-zone-latest.osm.pbf"
OUTPUT_FILE = "chennai_roads.geojson"

# Greater Chennai Corporation Exact Bounding Box
MIN_LAT, MIN_LON = 12.90, 80.12
MAX_LAT, MAX_LON = 13.18, 80.32

print("Chennai ki saari small streets extract ho rahi hain (100% offline)...")

class ChennaiRoadHandler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.features = []

    def way(self, w):
        # Saari highway types filter karo (including small alleys)
        if "highway" in w.tags:
            hw = w.tags["highway"]
            if hw in ["primary", "secondary", "tertiary", "residential", "living_street", "unclassified", "service"]:
                # Check nodes & coordinates
                coords = []
                for n in w.nodes:
                    if n.location.valid():
                        lat, lon = n.location.lat, n.location.lon
                        # Check bounding box
                        if MIN_LAT <= lat <= MAX_LAT and MIN_LON <= lon <= MAX_LON:
                            coords.append((round(lon, 6), round(lat, 6)))

                if len(coords) >= 2:
                    props = {
                        "name": w.tags.get("name", ""),
                        "highway": hw,
                        "surface": w.tags.get("surface", "")
                    }
                    self.features.append({
                        "type": "Feature",
                        "geometry": {
                            "type": "LineString",
                            "coordinates": coords
                        },
                        "properties": props
                    })

handler = ChennaiRoadHandler()
handler.apply_file(PBF_FILE, locations=True)

geojson_data = {
    "type": "FeatureCollection",
    "features": handler.features
}

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(geojson_data, f)

print(f"\nSUCCESS! Total {len(handler.features)} streets extract ho kar '{OUTPUT_FILE}' me save ho gayi!")