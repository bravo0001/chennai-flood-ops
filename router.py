import networkx as nx
import math

class FloodRouter:
    def __init__(self, geojson_data):
        self.graph = nx.Graph()
        self.build_base_graph(geojson_data)
        self.ensure_connected_network()

    def haversine(self, lat1, lon1, lat2, lon2):
        R = 6371000  # meters
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def build_base_graph(self, data):
        for feat in data.get("features", []):
            coords = feat.get("geometry", {}).get("coordinates", [])
            fid = feat.get("id")
            if len(coords) >= 2:
                # Har consecutive point ko edge banao taaki saare intermediate intersections connect hon
                for i in range(len(coords) - 1):
                    u = (round(coords[i][1], 5), round(coords[i][0], 5))
                    v = (round(coords[i+1][1], 5), round(coords[i+1][0], 5))
                    dist = max(1.0, self.haversine(u[0], u[1], v[0], v[1]))
                    self.graph.add_edge(u, v, weight=dist, distance=dist, coords=[coords[i], coords[i+1]], fid=fid)

    def ensure_connected_network(self):
        # Chhote dead-end components ko main arterial road network se snap karna
        if not self.graph.nodes:
            return
        components = sorted(nx.connected_components(self.graph), key=len, reverse=True)
        if len(components) > 1:
            main_comp = components[0]
            for comp in components[1:30]:  # Top subgraphs connect karo
                sample_u = next(iter(comp))
                nearest_v = min(main_comp, key=lambda v: self.haversine(sample_u[0], sample_u[1], v[0], v[1]))
                d = self.haversine(sample_u[0], sample_u[1], nearest_v[0], nearest_v[1])
                if d < 500:  # 500m ke andar bridge bana do
                    self.graph.add_edge(sample_u, nearest_v, weight=d, distance=d, coords=[[sample_u[1], sample_u[0]], [nearest_v[1], nearest_v[0]]], fid=-1)

    def update_flood_weights(self, flood_depths_dict):
        for u, v, data in self.graph.edges(data=True):
            fid = data.get("fid")
            depth = flood_depths_dict.get(fid, 0.0)
            dist = data["distance"]

            # Safe routing weight:
            # Depth > 7 cm: Strict Block (10,000x)
            # Depth 1.5 - 7 cm: Exponential Water Resistance
            if depth > 7.0:
                penalty = 10000.0
            elif depth >= 1.5:
                penalty = 1.0 + (depth * 2.5)  # Jitna zyada paani, utna zyada avoidance
            else:
                penalty = 1.0

            data["weight"] = dist * penalty
            data["depth"] = depth

    def extract_path_geometry(self, path_nodes):
        coords = []
        total_dist = 0.0
        flooded_segments = 0
        for i in range(len(path_nodes) - 1):
            data = self.graph.get_edge_data(path_nodes[i], path_nodes[i+1])
            coords.extend(data.get("coords", []))
            total_dist += data.get("distance", 0.0)
            if data.get("depth", 0.0) > 7.0:
                flooded_segments += 1
        return coords, round(total_dist / 1000.0, 2), max(1, round((total_dist / 1000.0) * 2.2)), flooded_segments

    def find_safe_path(self, start_lat, start_lon, end_lat, end_lon):
        # Major connected component se search karo taaki path guaranteed mile
        components = sorted(nx.connected_components(self.graph), key=len, reverse=True)
        main_nodes = list(components[0])

        start_node = min(main_nodes, key=lambda n: self.haversine(start_lat, start_lon, n[0], n[1]))
        end_node = min(main_nodes, key=lambda n: self.haversine(end_lat, end_lon, n[0], n[1]))

        try:
            # 1. NORMAL / FASTEST ROUTE (Sirf shortest distance dekhega, ignores flood)
            normal_nodes = nx.astar_path(
                self.graph, start_node, end_node,
                heuristic=lambda a, b: self.haversine(a[0], a[1], b[0], b[1]),
                weight="distance"
            )
            n_coords, n_dist, n_time, n_flooded = self.extract_path_geometry(normal_nodes)

            # 2. FLOOD-AWARE SAFE ROUTE (Penalized flooded roads)
            safe_nodes = nx.astar_path(
                self.graph, start_node, end_node,
                heuristic=lambda a, b: self.haversine(a[0], a[1], b[0], b[1]),
                weight="weight"
            )
            s_coords, s_dist, s_time, s_flooded = self.extract_path_geometry(safe_nodes)

            return {
                "status": "success",
                "normal_route": {
                    "coordinates": n_coords,
                    "distance_km": n_dist,
                    "est_time_min": n_time,
                    "flooded_segments": n_flooded
                },
                "safe_route": {
                    "coordinates": s_coords,
                    "distance_km": s_dist,
                    "est_time_min": s_time,
                    "flooded_segments": s_flooded
                }
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}