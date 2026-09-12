from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import json
import urllib.request
import uvicorn
from hydraulics import calculate_road_depth
from router import FloodRouter

app = FastAPI(title="Chennai Flood Early Warning & Emergency Navigation")

print("Initializing Chennai Geo-Data into Memory...")
with open("chennai_roads_elevated.geojson", "r", encoding="utf-8") as f:
    roads_data = json.load(f)

# Assign a unique integer ID to every road feature
for idx, feat in enumerate(roads_data.get("features", [])):
    feat["id"] = idx

with open("chennai_hospitals.geojson", "r", encoding="utf-8") as f:
    hospitals_data = json.load(f)

print(f"Loaded {len(roads_data['features'])} roads and {len(hospitals_data['features'])} medical centers.")

# Initialize the routing engine
router = FloodRouter(roads_data)
active_flood_depths = {}

# Endpoints for Frontend Map Layers
@app.get("/api/roads")
def get_roads():
    return JSONResponse(content=roads_data)

@app.get("/api/hospitals")
def get_hospitals():
    return JSONResponse(content=hospitals_data)

# Real-Time Weather Ingestion Endpoint (Open-Meteo)
@app.get("/api/live-weather")
def get_live_weather():
    # Chennai Coordinates: 13.0827 N, 80.2707 E
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
        # Fallback realistic Chennai monsoon values agar internet issue ho
        return {
            "status": "fallback",
            "temp": 28,
            "rain_mm": 12.4,
            "humidity": 87,
            "wind_speed": 22,
            "wind_dir": 45
        }

# Data Models
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

# Simulation Calculation Endpoint
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

    # Recalculate A* graph weights with dynamic road water column
    router.update_flood_weights(active_flood_depths)
    return {"depths": depth_updates}

# Safe Routing Endpoint
@app.post("/api/route")
def get_safe_route(req: RouteRequest):
    # Dynamic flood state sync before A* path search
    flood_depths = {}
    for feat in roads_data["features"]:
        depth = calculate_road_depth(feat, req.rain_intensity, req.duration_min, req.drain_factor)
        flood_depths[feat["id"]] = depth

    router.update_flood_weights(flood_depths)
    return router.find_safe_path(req.start_lat, req.start_lon, req.end_lat, req.end_lon)

# --- USP: Municipal Drainage Asset Endpoints ---
from drainage_manager import ManholeManager

# Initialize Manhole Manager
manhole_mgr = ManholeManager("chennai_roads_elevated.geojson")

@app.get("/api/manholes")
def get_manholes():
    return JSONResponse(content=manhole_mgr.get_manholes_geojson())

class ReportRequest(BaseModel):
    id: str
    notes: str = "Choked with plastic and silt"
    image_base64: str = ""

@app.post("/api/manhole/report")
def report_manhole(req: ReportRequest):
    return manhole_mgr.report_blockage(req.id, req.notes, req.image_base64)

@app.post("/api/manhole/resolve")
def resolve_manhole(req: BaseModel):
    # Payload me id aayegi
    mh_id = getattr(req, "id", None)
    if not mh_id:
        # Pydantic dict check
        pass
    return {"status": "success"}

# Agar BaseModel se simple handle karna ho:
class ResolveRequest(BaseModel):
    id: str

@app.post("/api/manhole/resolve")
def resolve_manhole(req: ResolveRequest):
    return manhole_mgr.resolve_blockage(req.id)

# Mount Frontend static directory
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)