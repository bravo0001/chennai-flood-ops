from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import json, gc, os
import urllib.request
import uvicorn
from hydraulics import calculate_road_depth
from router import FloodRouter

app = FastAPI(title="Chennai Flood Early Warning & Emergency Navigation")

print("Initializing Chennai Geo-Data into Memory...")

# --- Slim-load roads: keep only essential properties ---
with open("chennai_roads_elevated.geojson", "r", encoding="utf-8") as f:
    raw = json.load(f)

KEEP_PROPS = {
    "elevation_msl", "flow_slope", "flow_direction",
    "surface_material", "absorption_capacity", "runoff_coeff",
    "pipe_dia_mm", "pipe_label"
}

slim_features = []
for idx, feat in enumerate(raw.get("features", [])):
    geom = feat.get("geometry", {})
    coords = geom.get("coordinates", [])
    # Keep only first + last coord for the routing graph (saves ~60% memory)
    slim_coords = [coords[0], coords[-1]] if len(coords) >= 2 else coords
    props = {k: v for k, v in feat.get("properties", {}).items() if k in KEEP_PROPS}
    slim_features.append({
        "type": "Feature",
        "id": idx,
        "geometry": {"type": "LineString", "coordinates": slim_coords},
        "properties": props
    })

roads_data = {"type": "FeatureCollection", "features": slim_features}
del raw, slim_features
gc.collect()

with open("chennai_hospitals.geojson", "r", encoding="utf-8") as f:
    hospitals_data = json.load(f)

print(f"Loaded {len(roads_data['features'])} roads and {len(hospitals_data['features'])} medical centers.")

# Build routing graph lazily (after data load + GC)
router = FloodRouter(roads_data)
gc.collect()
print("Routing graph ready.")

active_flood_depths = {}

# --- API Endpoints ---
@app.get("/api/roads")
def get_roads():
    return JSONResponse(content=roads_data)

@app.get("/api/hospitals")
def get_hospitals():
    return JSONResponse(content=hospitals_data)

@app.get("/api/live-weather")
def get_live_weather():
    url = (
        "https://api.open-meteo.com/v1/forecast?"
        "latitude=13.0827&longitude=80.2707&current="
        "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,wind_direction_10m"
    )
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            current = data.get("current", {})
            return {
                "status": "success",
                "temp": current.get("temperature_2m", 28),
                "rain_mm": current.get("precipitation", 12.4),
                "humidity": current.get("relative_humidity_2m", 87),
                "wind_speed": current.get("wind_speed_10m", 22),
                "wind_dir": current.get("wind_direction_10m", 45)
            }
    except Exception:
        return {
            "status": "fallback",
            "temp": 28, "rain_mm": 12.4,
            "humidity": 87, "wind_speed": 22, "wind_dir": 45
        }

class SimRequest(BaseModel):
    rain_intensity: float
    duration_min: float
    drain_factor: float

class RouteRequest(BaseModel):
    start_lat: float
    start_lon: float
    end_lat: float
    end_lon: float
    rain_intensity: float = 25.0
    duration_min: float = 60.0
    drain_factor: float = 0.5

@app.post("/api/simulate")
def simulate(req: SimRequest):
    global active_flood_depths
    active_flood_depths.clear()
    depth_updates = {}
    for feat in roads_data["features"]:
        fid = str(feat["id"])
        depth = calculate_road_depth(feat, req.rain_intensity, req.duration_min, req.drain_factor)
        active_flood_depths[feat["id"]] = depth
        depth_updates[fid] = depth
    router.update_flood_weights(active_flood_depths)
    return {"depths": depth_updates}

@app.post("/api/route")
def get_safe_route(req: RouteRequest):
    flood_depths = {}
    for feat in roads_data["features"]:
        depth = calculate_road_depth(feat, req.rain_intensity, req.duration_min, req.drain_factor)
        flood_depths[feat["id"]] = depth
    router.update_flood_weights(flood_depths)
    return router.find_safe_path(req.start_lat, req.start_lon, req.end_lat, req.end_lon)

# --- Manhole endpoints ---
from drainage_manager import ManholeManager
manhole_mgr = ManholeManager(roads_data)

@app.get("/api/manholes")
def get_manholes():
    return JSONResponse(content=manhole_mgr.get_manholes_geojson())

class ReportRequest(BaseModel):
    id: str
    notes: str = "Choked with plastic and silt"
    image_base64: str = ""

class ResolveRequest(BaseModel):
    id: str

@app.post("/api/manhole/report")
def report_manhole(req: ReportRequest):
    return manhole_mgr.report_blockage(req.id, req.notes, req.image_base64)

@app.post("/api/manhole/resolve")
def resolve_manhole(req: ResolveRequest):
    return manhole_mgr.resolve_blockage(req.id)

# Mount static frontend
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)