import math
import folium
import requests

# 1. Chennai ke kuch specific key checkpoints (Lat, Lon)
# T. Nagar, Velachery, Guindy, Saidapet, Adyar, Marina
LOCATIONS = [
    {"name": "Velachery (Lake Area)", "lat": 12.9750, "lon": 80.2206},
    {"name": "T. Nagar (Usman Road)", "lat": 13.0418, "lon": 80.2341},
    {"name": "Saidapet Bridge", "lat": 13.0213, "lon": 80.2231},
    {"name": "Guindy", "lat": 13.0067, "lon": 80.2025},
    {"name": "Adyar", "lat": 13.0012, "lon": 80.2565},
    {"name": "Marina Beach (Sea level boundary)", "lat": 13.0500, "lon": 80.2824},
]


def get_elevations(points):
  """Open Elevation API se sea level height (in meters) fetch karta hai"""
  print("Fetching elevation data from Open-Meteo Elevation API...")
  lats = ",".join([str(p["lat"]) for p in points])
  lons = ",".join([str(p["lon"]) for p in points])

  url = f"https://api.open-meteo.com/v1/elevation?latitude={lats}&longitude={lons}"
  response = requests.get(url).json()

  elevations = response.get("elevation", [])
  for idx, elev in enumerate(elevations):
    points[idx]["elevation"] = elev
  return points


def find_water_flow(points):
  """Har point se dekhta hai ki sabse nearest lowest point kaun sa hai"""
  flow_paths = []
  for p in points:
    lowest_target = None
    max_slope = 0

    for candidate in points:
      if p == candidate:
        continue

      # Distance calculation (in km approximation)
      d_lat = candidate["lat"] - p["lat"]
      d_lon = candidate["lon"] - p["lon"]
      dist_km = math.sqrt(d_lat**2 + d_lon**2) * 111

      # Elevation difference: positive matlab downward slope
      drop = p["elevation"] - candidate["elevation"]

      if drop > 0 and dist_km > 0:
        slope = drop / dist_km
        if slope > max_slope:
          max_slope = slope
          lowest_target = candidate

    if lowest_target:
      flow_paths.append({
          "from": p,
          "to": lowest_target,
          "drop": p["elevation"] - lowest_target["elevation"],
      })
  return flow_paths


# --- Execution starts here ---
data = get_elevations(LOCATIONS)
flows = find_water_flow(data)

# Chennai center coordinates par Leaflet Map setup
m = folium.Map(location=[13.03, 80.23], zoom_start=12, tiles="CartoDB positron")

# Sabhi points map par mark karo
for pt in data:
  elev = pt["elevation"]
  # Agar sea level se 5-6 meter se kam unchai hai, toh waterlogging risk high hai
  is_high_risk = elev <= 7.0
  color = "red" if is_high_risk else "blue"

  popup_html = f"""
    <b>{pt['name']}</b><br>
    Elevation: <b>{elev} m</b> above sea level<br>
    Status: <b>{'High Flood/Waterlogging Risk' if is_high_risk else 'Moderate/Safe'}</b>
    """

  folium.CircleMarker(
      location=[pt["lat"], pt["lon"]],
      radius=8,
      color=color,
      fill=True,
      fill_color=color,
      fill_opacity=0.8,
      popup=popup_html,
  ).add_to(m)

# Water flow ki direction draw karo (Blue lines from high to low)
for flow in flows:
  p1 = [flow["from"]["lat"], flow["from"]["lon"]]
  p2 = [flow["to"]["lat"], flow["to"]["lon"]]

  folium.PolyLine(
      locations=[p1, p2],
      color="#0066cc",
      weight=3,
      dash_array="5, 10",
      tooltip=(
          f"Water flow from {flow['from']['name']} ({flow['from']['elevation']}m)"
          f" -> {flow['to']['name']} ({flow['to']['elevation']}m)"
      ),
  ).add_to(m)

# HTML file save karo
output_file = "chennai_water_map.html"
m.save(output_file)
print(
    f"\nMap ban gaya hai! '{output_file}' ko kisi bhi browser me open karo."
)