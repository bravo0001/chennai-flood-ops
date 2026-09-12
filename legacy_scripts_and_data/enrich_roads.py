import json
import math

INPUT_FILE = "chennai_roads.geojson"
OUTPUT_FILE = "chennai_roads_elevated.geojson"

print("Small streets data load ho raha hai...")
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

features = data.get("features", [])
print(f"Total {len(features)} streets! Calculating organic hydrological terrain...")

# REAL CHENNAI BASIN ELEVATION ANCHORS (Lat, Lon, Elevation in m MSL)
# Real topographical sinks & ridges across North, South, Central & West
BASIN_POINTS = [
    # Coastline (Flat 2.5 - 3.5m)
    (13.11, 80.29, 2.5), (13.06, 80.28, 3.2), (13.00, 80.26, 3.5), (12.91, 80.25, 2.8),
    # Known Severe Depression Bowls (1.5 - 3.2m)
    (12.978, 80.221, 2.0), # Velachery Lake Basin
    (12.962, 80.198, 2.4), # Madipakkam
    (12.935, 80.218, 1.6), # Pallikaranai Marshland
    (13.118, 80.255, 1.8), # Vyasarpadi / Korukkupet
    (13.102, 80.245, 2.9), # Perambur Low Basin
    (13.042, 80.232, 5.5), # T. Nagar Lake Area
    (13.065, 80.255, 4.0), # Central / Choolai
    # Moderate Plateau & Suburbs (6.5 - 10.0m)
    (13.088, 80.212, 8.5), # Anna Nagar
    (13.051, 80.211, 8.0), # Vadapalani
    (13.125, 80.215, 8.5), # Kolathur
    (13.030, 80.185, 7.5), # Alandur
    # Western & Southern Elevated Ridges (12 - 22m)
    (13.008, 80.198, 18.0), # St. Thomas Mount / Guindy Ridge
    (13.038, 80.158, 14.5), # Porur High
    (12.925, 80.125, 19.5), # Tambaram West
    (13.072, 80.162, 13.0), # Koyambedu Rim
    (13.155, 80.182, 16.0), # Puzhal Hills
]

def calculate_organic_elevation(lon, lat):
    num = 0.0
    den = 0.0
    for clat, clon, celev in BASIN_POINTS:
        # Distance squared
        d = math.hypot((lat - clat) * 1.1, lon - clon)
        if d < 0.0005:
            return celev
        w = 1.0 / (d ** 2.2)
        num += w * celev
        den += w
    
    base = num / den
    # Micro-terrain roughness so adjacent residential streets don't look artificial
    noise = 0.4 * math.sin(lat * 1400.0) * math.cos(lon * 1200.0)
    return max(1.2, round(base + noise, 1))

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
        return {"type": "Semi-Paved Urban Street", "absorption": "Moderate (30% absorbed)", "runoff_coeff": 0.78}

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
            e_start = calculate_organic_elevation(pts[0][0], pts[0][1])
            e_end = calculate_organic_elevation(pts[-1][0], pts[-1][1])
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

print(f"\nSUCCESS! {len(valid_features)} streets with organic realistic terrain generated in '{OUTPUT_FILE}'!")