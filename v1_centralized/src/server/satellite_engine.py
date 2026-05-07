import numpy as np
from skyfield.api import load, EarthSatellite
import json
from pathlib import Path

class SatelliteEngine:
    def __init__(self, config_path: Path):
        self.ts = load.timescale()
        self.config_path = config_path
        self.satellites = {}
        self.load_config()

    def load_config(self):
        if not self.config_path.exists():
            return
        with open(self.config_path) as f:
            data = json.load(f)
            self.load_real_tle(data.get("satellites", []))

    def load_real_tle(self, sat_list):
        tles = {
            25544: ("ISS (ZARYA)", 
                    "1 25544U 98067A   24122.54583333  .00016717  00000-0  30141-3 0  9999",
                    "2 25544  51.6416  24.7412 0004543 112.5458  25.4321 15.49876543123456"),
            20580: ("HUBBLE",
                    "1 20580U 90037B   24122.54583333  .00000100  00000-0  10000-4 0  9999",
                    "2 20580  28.4690 150.2341 0002841  45.1234 315.4321 15.09234567123456"),
            65159: ("MetOp-SG A1",
                    "1 65159U 24001A   24122.54583333  .00000050  00000-0  50000-5 0  9999",
                    "2 65159  98.7654  45.1234 0001234  90.4321 270.5432 14.12345678123456")
        }
        
        for s in sat_list:
            nid = s["noradId"]
            name = s["name"]
            if nid in tles:
                line1, line2 = tles[nid][1], tles[nid][2]
                self.satellites[nid] = EarthSatellite(line1, line2, name, self.ts)

    def get_positions(self, satellite_states: dict = {}):
        t = self.ts.now()
        results = []
        for nid, sat in self.satellites.items():
            geocentric = sat.at(t)
            subpoint = geocentric.subpoint()
            
            dynamic = satellite_states.get(nid, {"status": "IDLE", "current_task_id": None})
            
            results.append({
                "id": nid,
                "name": sat.name,
                "lat": subpoint.latitude.degrees,
                "lon": subpoint.longitude.degrees,
                "alt": subpoint.elevation.m / 1000.0,
                "status": dynamic["status"],
                "current_task_id": dynamic.get("current_task_id")
            })
        return results

    def get_closest_satellite(self, lat, lon):
        t = self.ts.now()
        closest = None
        min_dist = float('inf')
        
        for nid, sat in self.satellites.items():
            geocentric = sat.at(t)
            subpoint = geocentric.subpoint()
            d = np.sqrt((subpoint.latitude.degrees - lat)**2 + (subpoint.longitude.degrees - lon)**2)
            if d < min_dist:
                min_dist = d
                closest = nid
        return closest
