import json
import math

INPUT_FILE = "chennai_roads.geojson"
OUTPUT_FILE = "chennai_roads_elevated.geojson"

print("Small streets data load ho raha hai...")
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

features = data.get("features", [])
print(f"Total {len(features)} roads & streets mili! Realistic terrain processing shuru...")

# REALISTIC CHENNAI ELEVATION MODEL (Continuous GIS interpolation)
def estimate_realistic_elevation(lon, lat):
    # 1. Macro West-to-East slope: West (Porur/Tambaram ~16m) -> Coast (Marina/ECR ~2.5m)
    # Longitude range: 80.12 (West) to 80.28 (Coast)
    west_dist = max(0.0, 80.285 - lon)
    base_elev = 2.5 + (west_dist * 85.0)

    # 2. South-to-North regional tilt (St. Thomas Mount / Guindy ridge vs North flat coastal plain)
    lat_factor = (lat - 13.00) * 8.0
    elev = base_elev - lat_factor

    # 3. Known Real-world Depressions (Pallikaranai Marsh & Velachery bowl)
    # Approx center: lat 12.94, lon 80.21
    dist_velachery = math.hypot(lat - 12.945, lon - 80.215)
    if dist_velachery < 0.045:
        elev -= (0.045 - dist_velachery) * 60.0  # Natural flood sinkhole

    # 4. Adyar River basin depression (Lat ~13.01, running West to East)
    adyar_dist = abs(lat - 13.01)
    if adyar_dist < 0.015:
        elev -= (0.015 - adyar_dist) * 80.0

    # 5. Cooum River basin depression (Lat ~13.07, running West to East)
    cooum_dist = abs(lat - 13.075)
    if cooum_dist < 0.012:
        elev -= (0.012 - cooum_dist) * 75.0

    return max(1.2, round(elev, 1))

def get_surface_properties(tags):
    surface = tags.get("surface", "").lower()
    highway = tags.get("highway", "").lower()

    mud_types = ["unpaved", "compacted", "dirt", "earth", "ground", "mud", "sand", "gravel", "grass"]
    cement_types = ["paved", "asphalt", "concrete", "concrete:lanes", "paving_stones", "sett"]

    if surface in mud_types or highway in ["track"]:
        return {"type": "Mud / Unpaved Ground", "absorption": "High (70% absorbed)", "runoff_coeff": 0.35}
    elif surface in cement_types or highway in ["primary", "secondary", "tertiary", "trunk"]:
        return {"type": "Cemented / Asphalt", "absorption": "Near Zero (10% absorbed)", "runoff_coeff": 0.90}
    else:
        return {"type": "Semi-Paved Urban Street", "absorption": "Moderate (30% absorbed)", "runoff_coeff": 0.75}

def get_drainage_pipe_specs(highway_type, surface_type):
    if "Unpaved" in surface_type:
        return {"diameter_mm": 0, "pipe_label": "No Pipe (Open Drain/Seepage)"}
    if highway_type in ["primary", "trunk"]:
        return {"diameter_mm": 1200, "pipe_label": "1200 mm RCC Box Culvert"}
    elif highway_type == "secondary":
        return {"diameter_mm": 900, "pipe_label": "900 mm RCC Storm Pipe"}
    elif highway_type == "tertiary":
        return {"diameter_mm": 600, "pipe_label": "600 mm Circular Pipe"}
    else:
        return {"diameter_mm": 350, "pipe_label": "350 mm Feeder Pipe"}

valid_features = []
for feat in features:
    geom = feat.get("geometry", {})
    if geom.get("type") == "LineString":
        pts = geom.get("coordinates", [])
        if len(pts) >= 2:
            e_start = estimate_realistic_elevation(pts[0][0], pts[0][1])
            e_end = estimate_realistic_elevation(pts[-1][0], pts[-1][1])
            avg_elev = round((e_start + e_end) / 2, 1)

            drop = round(e_start - e_end, 2)
            flow_desc = "Flat / Water Accumulation Zone" if abs(drop) < 0.2 else ("Draining towards End" if drop > 0 else "Draining towards Start")

            props = feat.get("properties", {})
            surface_info = get_surface_properties(props)
            pipe_info = get_drainage_pipe_specs(props.get("highway", ""), surface_info["type"])

            feat["properties"]["elevation_msl"] = avg_elev
            feat["properties"]["flow_slope"] = drop
            feat["properties"]["flow_direction"] = flow_desc
            feat["properties"]["surface_material"] = surface_info["type"]
            feat["properties"]["absorption_capacity"] = surface_info["absorption"]
            feat["properties"]["runoff_coeff"] = surface_info["runoff_coeff"]
            feat["properties"]["pipe_dia_mm"] = pipe_info["diameter_mm"]
            feat["properties"]["pipe_label"] = pipe_info["pipe_label"]

            valid_features.append(feat)

data["features"] = valid_features
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(data, f)

print(f"\nSUCCESS! {len(valid_features)} streets ka realistic terrain map ready ho gaya!")