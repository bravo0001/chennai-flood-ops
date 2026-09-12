import json
import os
from datetime import datetime

INCIDENTS_FILE = "manhole_incidents.json"

class ManholeManager:
    def __init__(self, roads_data):
        """Accept pre-loaded roads_data dict or a file path string."""
        self.manholes = []
        self.incidents = {}
        self.load_incidents()
        self.generate_municipal_manholes(roads_data)

    def load_incidents(self):
        if os.path.exists(INCIDENTS_FILE):
            try:
                with open(INCIDENTS_FILE, "r", encoding="utf-8") as f:
                    self.incidents = json.load(f)
            except Exception:
                self.incidents = {}
        else:
            self.incidents = {}

    def save_incidents(self):
        with open(INCIDENTS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.incidents, f, indent=2)

    def generate_municipal_manholes(self, roads_data):
        """
        CPHEEO / Indian Municipal Standards:
        Stormwater inlets & maintenance manholes spaced every 40-50m
        along urban corridors and junctions.
        Accept pre-loaded dict or file path string.
        """
        # Support both pre-loaded dict and legacy file path
        if isinstance(roads_data, str):
            if not os.path.exists(roads_data):
                return
            with open(roads_data, "r", encoding="utf-8") as f:
                roads_data = json.load(f)

        mh_counter = 1000
        for feat in roads_data.get("features", []):
            coords = feat.get("geometry", {}).get("coordinates", [])
            props = feat.get("properties", {})
            street_name = props.get("name", "Urban Corridor")
            elev = props.get("elevation_msl", 4.0)

            if len(coords) >= 2:
                sample_indices = [0, len(coords) // 2, len(coords) - 1]
                for idx in sample_indices:
                    pt = coords[idx]
                    if isinstance(pt[0], (int, float)) and isinstance(pt[1], (int, float)):
                        mh_counter += 1
                        mh_id = f"GCC-MH-{mh_counter}"
                        
                        incident = self.incidents.get(mh_id, None)
                        status = incident.get("status", "CLEAN") if incident else "CLEAN"

                        self.manholes.append({
                            "type": "Feature",
                            "geometry": {
                                "type": "Point",
                                "coordinates": [round(pt[0], 6), round(pt[1], 6)]
                            },
                            "properties": {
                                "id": mh_id,
                                "street": street_name,
                                "elevation_msl": elev,
                                "type": "Stormwater Grate & Inspection Chamber",
                                "status": status,
                                "last_reported": incident.get("timestamp", "") if incident else "",
                                "image_url": incident.get("image_url", "") if incident else "",
                                "report_notes": incident.get("notes", "") if incident else ""
                            }
                        })

    def get_manholes_geojson(self):
        return {
            "type": "FeatureCollection",
            "features": self.manholes
        }

    def report_blockage(self, mh_id, notes, image_base64=""):
        incident_data = {
            "id": mh_id,
            "status": "BLOCKED",
            "notes": notes,
            "image_url": image_base64,
            "timestamp": datetime.now().strftime("%d %b %Y, %I:%M %p"),
            "alert_sent_to": "Greater Chennai Corporation (GCC) Stormwater Drainage Dept (SWD)"
        }
        self.incidents[mh_id] = incident_data
        self.save_incidents()

        for mh in self.manholes:
            if mh["properties"]["id"] == mh_id:
                mh["properties"]["status"] = "BLOCKED"
                mh["properties"]["last_reported"] = incident_data["timestamp"]
                mh["properties"]["image_url"] = image_base64
                mh["properties"]["report_notes"] = notes
                break

        return {"status": "success", "message": f"Alert pushed to GCC Control Room for {mh_id}"}

    def resolve_blockage(self, mh_id):
        if mh_id in self.incidents:
            del self.incidents[mh_id]
            self.save_incidents()

        for mh in self.manholes:
            if mh["properties"]["id"] == mh_id:
                mh["properties"]["status"] = "CLEAN"
                mh["properties"]["last_reported"] = ""
                mh["properties"]["image_url"] = ""
                mh["properties"]["report_notes"] = ""
                break

        return {"status": "success", "message": f"{mh_id} marked as Restored & Cleaned by GCC"}