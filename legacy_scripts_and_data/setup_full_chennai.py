import os
import json
import requests
import osmium

PBF_FILE = "southern-zone-latest.osm.pbf"
OUTPUT_FILE = "chennai_roads.geojson"
DOWNLOAD_URL = "https://download.geofabrik.de/asia/india/southern-zone-latest.osm.pbf"

# Greater Chennai Corporation Bounding Box
MIN_LAT, MIN_LON = 12.90, 80.12
MAX_LAT, MAX_LON = 13.18, 80.32

# 1. Download PBF automatically if not already downloaded
if not os.path.exists(PBF_FILE):
    print(f"File download shuru ho rahi hai (~530 MB)...")
    print("Internet speed ke hisab se 2-4 minute lagenge, please wait...")
    with requests.get(DOWNLOAD_URL, stream=True) as r:
        r.raise_for_status()
        total_size = int(r.headers.get('content-length', 0))
        downloaded = 0
        with open(PBF_FILE, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    mb = downloaded / (1024 * 1024)
                    print(f"Downloaded: {mb:.1f} MB / {total_size / (1024 * 1024):.1f} MB", end="\r")
    print("\nDownload complete!")
else:
    print(f"'{PBF_FILE}' pehle se folder me hai. Download skip kar rahe hain.")

# 2. Extract complete Chennai road network
print("\nAb Chennai ki saari galliyan (residential, living_street, etc.) extract ho rahi hain...")

class ChennaiRoadHandler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.features = []

    def way(self, w):
        if "highway" in w.tags:
            hw = w.tags["highway"]
            if hw in ["primary", "secondary", "tertiary", "residential", "living_street", "unclassified", "service"]:
                coords = []
                for n in w.nodes:
                    if n.location.valid():
                        lat, lon = n.location.lat, n.location.lon
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