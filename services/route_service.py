import os
import requests

ORS_API_KEY = os.environ.get("OPENROUTESERVICE_API_KEY", "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjRjMDhmYjZjNzYxYzRkN2E4MDJiODcxMTkzMWEwMzRkIiwiaCI6Im11cm11cjY0In0=")
ORS_BASE_URL = "https://api.openrouteservice.org/v2/directions/driving-car"
OSRM_BASE_URL = "http://router.project-osrm.org/route/v1/driving"

def get_route_ors(start_lon, start_lat, end_lon, end_lat):
    headers = {"Authorization": ORS_API_KEY, "Content-Type": "application/json"}
    body = {"coordinates": [[start_lon, start_lat], [end_lon, end_lat]], "format": "geojson"}
    try:
        resp = requests.post(f"{ORS_BASE_URL}/geojson", headers=headers, json=body, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        coords = data["features"][0]["geometry"]["coordinates"]
        summary = data["features"][0]["properties"]["summary"]
        return {
            "coordinates": [[c[1], c[0]] for c in coords],
            "distance_m": summary.get("distance", 0),
            "duration_s": summary.get("duration", 0),
            "source": "ors"
        }
    except Exception as e:
        print(f"ORS error: {e}")
        return get_route_osrm(start_lon, start_lat, end_lon, end_lat)

def get_route_osrm(start_lon, start_lat, end_lon, end_lat):
    url = f"{OSRM_BASE_URL}/{start_lon},{start_lat};{end_lon},{end_lat}?overview=full&geometries=geojson"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        route = data["routes"][0]
        coords = route["geometry"]["coordinates"]
        return {
            "coordinates": [[c[1], c[0]] for c in coords],
            "distance_m": route["distance"],
            "duration_s": route["duration"],
            "source": "osrm"
        }
    except Exception as e:
        print(f"OSRM error: {e}")
        return {"coordinates": [[start_lat, start_lon], [end_lat, end_lon]], "distance_m": 0, "duration_s": 0, "source": "fallback"}

def get_full_route(ambulance_lat, ambulance_lon, user_lat, user_lon, hospital_lat, hospital_lon):
    leg1 = get_route_ors(ambulance_lon, ambulance_lat, user_lon, user_lat)
    leg2 = get_route_ors(user_lon, user_lat, hospital_lon, hospital_lat)
    combined_coords = leg1["coordinates"] + leg2["coordinates"]
    total_distance = leg1["distance_m"] + leg2["distance_m"]
    total_duration = leg1["duration_s"] + leg2["duration_s"]
    return {
        "full_route": combined_coords,
        "leg1": leg1,
        "leg2": leg2,
        "total_distance_km": round(total_distance / 1000, 2),
        "total_duration_min": round(total_duration / 60, 1)
    }
