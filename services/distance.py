import math

EARTH_RADIUS_KM = 6371.0

def haversine(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return EARTH_RADIUS_KM * c

def estimated_time_minutes(distance_km, speed_kmh=40):
    return round((distance_km / speed_kmh) * 60, 1)

def sort_by_distance(user_lat, user_lon, locations):
    results = []
    for loc in locations:
        try:
            lat = float(loc.get("latitude") or loc.get("lat", 0))
            lon = float(loc.get("longitude") or loc.get("lon", 0))
            dist = haversine(user_lat, user_lon, lat, lon)
            entry = dict(loc)
            entry["distance_km"] = round(dist, 2)
            entry["eta_minutes"] = estimated_time_minutes(dist)
            results.append(entry)
        except (ValueError, TypeError):
            continue
    return sorted(results, key=lambda x: x["distance_km"])
