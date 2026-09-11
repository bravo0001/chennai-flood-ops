import json
import time
import requests

OUTPUT_FILE = "chennai_roads.geojson"

# Fast mirror endpoint
API_URL = "https://overpass.kumi.systems/api/interpreter"

# Chennai ko 4 equal zones me split kiya (Taaki request timeout na ho)
ZONES = [
    {"name": "Central Core (T. Nagar, Kodambakkam, Nungambakkam)", "bbox": "13.01,80.18,13.08,80.26"},
    {"name": "South Zone (Velachery, Guindy, Adyar, Thiruvanmiyur)", "bbox": "12.92,80.18,13.01,80.27"},
    {"name": "North Zone (George Town, Royapuram, Perambur)", "bbox": "13.08,80.18,13.16,80.30"},
    {"name": "West Zone (Porur, Koyambedu, Mogappair)", "bbox": "13.01,80.12,13.09,80.18"}
]

all_features = []
seen_ids = set()

print("Chunked download shuru ho raha hai taaki connection timeout na ho...\n")

for zone in ZONES:
    print(f"Fetching: {zone['name']}...")
    
    query = f"""
    [out:json][timeout:90];
    (
      way["highway"~"primary|secondary|tertiary|residential|living_street|unclassified"]({zone['bbox']});
    );
    out geom;
    """
    
    success = False
    for attempt in range(3):
        try:
            res = requests.post(API_URL, data={"data": query}, timeout=100)
            if res.status_code == 200:
                data = res.json()
                elements = data.get("elements", [])
                
                count = 0
                for el in elements:
                    el_id = el.get("id")
                    if el_id in seen_ids or "geometry" not in el or len(el["geometry"]) < 2:
                        continue
                    seen_ids.add(el_id)

                    geom = {
                        "type": "LineString",
                        "coordinates": [[pt["lon"], pt["lat"]] for pt in el["geometry"]]
                    }
                    all_features.append({
                        "type": "Feature",
                        "geometry": geom,
                        "properties": el.get("tags", {})
                    })
                    count += 1
                
                print(f"  -> Done! {count} streets add hui. Total abhi tak: {len(all_features)}")
                success = True
                break
            else:
                print(f"  -> Server busy (status {res.status_code}), retrying...")
                time.sleep(3)
        except Exception as e:
            print(f"  -> Timeout retry {attempt+1}/3...")
            time.sleep(4)
            
    if not success:
        print(f"Warning: {zone['name']} skip ho gaya timeout ki wajah se.")

# GeoJSON save
geojson_data = {
    "type": "FeatureCollection",
    "features": all_features
}

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(geojson_data, f)

print(f"\nSUCCESS! Poore Chennai ki {len(all_features)} streets '{OUTPUT_FILE}' me save ho gayi!")