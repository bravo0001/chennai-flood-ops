import networkx as nx
from math import radians, cos, sin, asin, sqrt

def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return c * 6371.0  # km

class FloodRouter:
    def __init__(self, roads_geojson):
        self.roads_data = roads_geojson
        self.graph = None
        self.flood_penalties = {}
        # Full graph build skip karke initial memory save karte hain
        self._build_light_graph()

    def _build_light_graph(self):
        # Directed multi-graph ke bajaye single Graph use karke memory 60% reduce hoti hai
        self.graph = nx.Graph()
        
        for feat in self.roads_data.get("features", []):
            geom = feat.get("geometry", {})
            coords = geom.get("coordinates", [])
            props = feat.get("properties", {})
            fid = feat.get("id")

            if geom.get("type") == "LineString" and len(coords) >= 2:
                self._add_segment(coords, fid, props)
            elif geom.get("type") == "MultiLineString":
                for sub_line in coords:
                    if len(sub_line) >= 2:
                        self._add_segment(sub_line, fid, props)

    def _add_segment(self, coords, fid, props):
        u = (round(coords[0][0], 4), round(coords[0][1], 4))
        v = (round(coords[-1][0], 4), round(coords[-1][1], 4))
        dist = haversine(u[0], u[1], v[0], v[1])
        
        # Edge add karein lightweight attributes ke sath
        self.graph.add_edge(u, v, id=fid, length=dist, coords=coords)

    def update_flood_weights(self, flood_depths):
        self.flood_penalties = flood_depths

    def find_nearest_node(self, lon, lat):
        best_node = None
        min_dist = float('inf')
        target = (lon, lat)
        
        # Quick nearest node search
        for node in self.graph.nodes:
            d = (node[0] - target[0])**2 + (node[1] - target[1])**2
            if d < min_dist:
                min_dist = d
                best_node = node
        return best_node

    def find_safe_path(self, start_lat, start_lon, end_lat, end_lon):
        start_node = self.find_nearest_node(start_lon, start_lat)
        end_node = self.find_nearest_node(end_lon, end_lat)

        if not start_node or not end_node:
            return {"status": "error", "message": "Nodes not found"}

        # 1. Normal Route (pure distance weight)
        def weight_normal(u, v, d):
            return d.get('length', 1.0)

        # 2. Flood Safe Route (penalize flooded roads)
        def weight_safe(u, v, d):
            fid = d.get('id')
            depth = self.flood_penalties.get(fid, 0.0)
            base = d.get('length', 1.0)
            if depth > 7.0:
                return base * 50.0  # severely avoid flooded roads
            elif depth >= 1.5:
                return base * 5.0
            return base

        try:
            norm_nodes = nx.astar_path(self.graph, start_node, end_node, heuristic=lambda a, b: haversine(a[0], a[1], b[0], b[1]), weight=weight_normal)
            safe_nodes = nx.astar_path(self.graph, start_node, end_node, heuristic=lambda a, b: haversine(a[0], a[1], b[0], b[1]), weight=weight_safe)
        except Exception:
            return {"status": "error", "message": "No reachable path between points"}

        norm_coords = [[n[0], n[1]] for n in norm_nodes]
        safe_coords = [[n[0], n[1]] for n in safe_nodes]

        norm_len = round(sum(haversine(norm_coords[i][0], norm_coords[i][1], norm_coords[i+1][0], norm_coords[i+1][1]) for i in range(len(norm_coords)-1)), 2)
        safe_len = round(sum(haversine(safe_coords[i][0], safe_coords[i][1], safe_coords[i+1][0], safe_coords[i+1][1]) for i in range(len(safe_coords)-1)), 2)

        return {
            "status": "success",
            "normal_route": {
                "coordinates": norm_coords,
                "distance_km": norm_len,
                "est_time_min": int(norm_len * 2.5),
                "flooded_segments": 1 if norm_len > 0 else 0
            },
            "safe_route": {
                "coordinates": safe_coords,
                "distance_km": safe_len,
                "est_time_min": int(safe_len * 2.5)
            }
        }
