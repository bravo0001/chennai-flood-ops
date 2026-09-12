import json
import osmium

PBF_FILE = "southern-zone-latest.osm.pbf"
OUTPUT_FILE = "chennai_hospitals.geojson"

# Greater Chennai Corporation Bounding Box
MIN_LAT, MIN_LON = 12.90, 80.12
MAX_LAT, MAX_LON = 13.18, 80.32

print("Chennai ke hospitals aur clinics local PBF file se extract ho rahe hain (Offline)...")

class HospitalHandler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.features = []

    def node(self, n):
        if "amenity" in n.tags and n.tags["amenity"] in ["hospital", "clinic", "doctors"]:
            if n.location.valid():
                lat, lon = n.location.lat, n.location.lon
                if MIN_LAT <= lat <= MAX_LAT and MIN_LON <= lon <= MAX_LON:
                    name = n.tags.get("name", "Medical Center / Clinic")
                    emergency = n.tags.get("emergency", "no")
                    self.features.append({
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [round(lon, 6), round(lat, 6)]
                        },
                        "properties": {
                            "name": name,
                            "emergency": emergency,
                            "type": n.tags["amenity"]
                        }
                    })

handler = HospitalHandler()
handler.apply_file(PBF_FILE, locations=True)

geojson_data = {
    "type": "FeatureCollection",
    "features": handler.features
}

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(geojson_data, f)

print(f"\nSUCCESS! Total {len(handler.features)} hospitals & medical facilities save ho gayi '{OUTPUT_FILE}' me!")