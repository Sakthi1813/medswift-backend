"""
ambulance_dispatcher.py
=======================
Real-time ambulance data via Gemini API.
- PRIMARY  : Gemini 2.0 Flash generates 8 realistic ambulances scattered within
             1–4.5 km of the user's actual GPS coordinates.
- FALLBACK : ambulances.json (repositioned around user coords if Gemini fails).

Each ambulance has: id, driver_name, driver_phone, vehicle_number,
latitude, longitude, status, type, hospital, distance_km, eta_minutes.
"""

import json, os, math, random, time, threading, re
import google.generativeai as genai
from services.distance import haversine

# ── Config ────────────────────────────────────────────────────
NEARBY_RADIUS_KM    = 5.0
SIMULATED_SPEED_KMH = 40
CACHE_TTL_SECONDS   = 10      # re-ask Gemini every 10 s (simulates live updates)

genai.configure(api_key=os.environ.get("GEMINI_API_KEY", ""))

_lock             = threading.Lock()
_cache            = {}          # keyed by (round(lat,2), round(lon,2))
_dispatched_ids   = {}          # id -> status  (persist across Gemini refreshes)

# ── Gemini fetch ──────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a real-time ambulance dispatch API for India.
Return ONLY a valid JSON array — no markdown, no explanation, no extra text.
Each element must have exactly these keys:
  id, driver_name, driver_phone, vehicle_number,
  latitude, longitude, status, type, hospital

Rules:
- Generate exactly 8 ambulances.
- All coordinates must be within 0.5–4.5 km of the given center point.
- Spread them in different directions (N, NE, E, SE, S, SW, W, NW).
- status: 6 must be "available", 2 must be "busy".
- type: mix of "ALS" and "BLS".
- Use realistic Indian names, DL-xx-XX-xxxx vehicle numbers.
- hospital: nearest real hospital name for that sub-area.
- latitude/longitude: float with 6 decimal places.
"""

def _fetch_from_gemini(user_lat: float, user_lon: float) -> list | None:
    prompt = (
        f"Generate 8 ambulances near latitude={user_lat:.6f}, longitude={user_lon:.6f}. "
        f"Return only the JSON array."
    )
    try:
        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            system_instruction=_SYSTEM_PROMPT,
            generation_config=genai.GenerationConfig(
                temperature=0.7,
                max_output_tokens=1200,
            )
        )
        response = model.generate_content(prompt)
        raw = response.text.strip()

        # Strip any accidental markdown fences
        raw = re.sub(r"^```[a-z]*\n?", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\n?```$", "", raw, flags=re.IGNORECASE)
        raw = raw.strip()

        data = json.loads(raw)
        if isinstance(data, list) and len(data) > 0:
            print(f"[Gemini] Fetched {len(data)} ambulances near ({user_lat:.4f}, {user_lon:.4f})")
            return data
    except Exception as e:
        print(f"[Gemini] Error: {e}")
    return None


# ── JSON fallback ─────────────────────────────────────────────

def _json_path():
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "ambulances.json")


def _load_json_fallback(user_lat: float, user_lon: float) -> list:
    """Load JSON and reposition each ambulance within 1–4.5 km of user."""
    try:
        with open(_json_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = _hardcoded_fallback()

    repositioned = []
    for i, a in enumerate(data):
        angle_deg = (i * 45) % 360          # spread in 8 directions
        dist_km   = 1.0 + (i % 4) * 0.9    # 1.0 / 1.9 / 2.8 / 3.7 km
        angle_rad = math.radians(angle_deg)
        dlat = (dist_km / 111.0) * math.cos(angle_rad)
        dlon = (dist_km / (111.0 * math.cos(math.radians(user_lat)))) * math.sin(angle_rad)
        entry = dict(a)
        entry["latitude"]  = round(user_lat + dlat, 6)
        entry["longitude"] = round(user_lon + dlon, 6)
        repositioned.append(entry)
    return repositioned


def _hardcoded_fallback():
    return [
        {"id": "AMB001", "driver_name": "Rajesh Kumar",  "driver_phone": "+91-9876543210",
         "vehicle_number": "DL-01-AB-1234", "latitude": 0, "longitude": 0,
         "status": "available", "type": "ALS", "hospital": "Nearest Hospital"},
        {"id": "AMB002", "driver_name": "Suresh Singh",  "driver_phone": "+91-9876543211",
         "vehicle_number": "DL-02-CD-5678", "latitude": 0, "longitude": 0,
         "status": "available", "type": "BLS", "hospital": "Nearest Hospital"},
        {"id": "AMB003", "driver_name": "Mohan Verma",   "driver_phone": "+91-9876543212",
         "vehicle_number": "DL-03-EF-9012", "latitude": 0, "longitude": 0,
         "status": "available", "type": "ALS", "hospital": "Nearest Hospital"},
        {"id": "AMB004", "driver_name": "Amit Sharma",   "driver_phone": "+91-9876543213",
         "vehicle_number": "DL-04-GH-3456", "latitude": 0, "longitude": 0,
         "status": "available", "type": "BLS", "hospital": "Nearest Hospital"},
        {"id": "AMB005", "driver_name": "Vikram Patel",  "driver_phone": "+91-9876543214",
         "vehicle_number": "DL-05-IJ-7890", "latitude": 0, "longitude": 0,
         "status": "available", "type": "ALS", "hospital": "Nearest Hospital"},
        {"id": "AMB006", "driver_name": "Deepak Yadav",  "driver_phone": "+91-9876543215",
         "vehicle_number": "DL-06-KL-2345", "latitude": 0, "longitude": 0,
         "status": "available", "type": "BLS", "hospital": "Nearest Hospital"},
        {"id": "AMB007", "driver_name": "Priya Mehta",   "driver_phone": "+91-9876543216",
         "vehicle_number": "DL-07-MN-6789", "latitude": 0, "longitude": 0,
         "status": "busy",      "type": "ALS", "hospital": "Nearest Hospital"},
        {"id": "AMB008", "driver_name": "Anil Gupta",    "driver_phone": "+91-9876543217",
         "vehicle_number": "DL-08-OP-0123", "latitude": 0, "longitude": 0,
         "status": "available", "type": "BLS", "hospital": "Nearest Hospital"},
    ]


# ── Simulate live GPS drift ───────────────────────────────────

def _apply_drift(ambulances: list) -> list:
    """Tiny random position drift to simulate live movement."""
    for a in ambulances:
        if a.get("status") == "available":
            a["latitude"]  = round(float(a["latitude"])  + (random.random() - 0.5) * 0.002, 6)
            a["longitude"] = round(float(a["longitude"]) + (random.random() - 0.5) * 0.002, 6)
    return ambulances


# ── Main cache + refresh logic ────────────────────────────────

def _get_cache_key(lat, lon):
    return (round(lat, 3), round(lon, 3))


def load_ambulances_for(user_lat: float, user_lon: float, force: bool = False) -> list:
    """
    Return ambulances for this user location.
    Uses Gemini if fresh data needed; falls back to JSON on error.
    Preserves dispatched/busy statuses across refreshes.
    """
    global _cache, _dispatched_ids

    key = _get_cache_key(user_lat, user_lon)
    now = time.time()

    with _lock:
        cached = _cache.get(key)
        needs_refresh = (
            cached is None or
            force or
            (now - cached["ts"]) > CACHE_TTL_SECONDS
        )

        if not needs_refresh:
            return _apply_drift(cached["data"])

    # --- outside lock: do the API call ---
    raw = _fetch_from_gemini(user_lat, user_lon)
    if raw is None:
        print("[Dispatcher] Using JSON fallback.")
        raw = _load_json_fallback(user_lat, user_lon)

    # Reapply any manually-set dispatched statuses
    for a in raw:
        if a.get("id") in _dispatched_ids:
            a["status"] = _dispatched_ids[a["id"]]

    with _lock:
        _cache[key] = {"data": raw, "ts": now}

    return _apply_drift(raw)


# ── Public API ────────────────────────────────────────────────

def find_nearby_ambulances(user_lat: float, user_lon: float,
                           radius_km: float = NEARBY_RADIUS_KM) -> list:
    """
    Return all ambulances within radius_km of the user,
    sorted: available-first, then by ascending distance.
    """
    ambulances = load_ambulances_for(user_lat, user_lon)
    nearby = []
    for a in ambulances:
        try:
            dist = haversine(user_lat, user_lon,
                             float(a["latitude"]), float(a["longitude"]))
            if dist <= radius_km:
                entry = dict(a)
                entry["distance_km"] = round(dist, 2)
                entry["eta_minutes"] = round((dist / SIMULATED_SPEED_KMH) * 60, 1)
                nearby.append(entry)
        except (ValueError, TypeError):
            continue

    nearby.sort(key=lambda x: (0 if x["status"] == "available" else 1, x["distance_km"]))
    return nearby


def find_nearest_ambulance(user_lat: float, user_lon: float):
    """Return the single nearest available ambulance (used by booking endpoint)."""
    nearby = find_nearby_ambulances(user_lat, user_lon)
    for a in nearby:
        if a["status"] == "available":
            return a
    return nearby[0] if nearby else None


def update_ambulance_status(ambulance_id: str, status: str,
                            lat=None, lon=None):
    """Persist status change across Gemini refreshes."""
    global _dispatched_ids, _cache
    _dispatched_ids[ambulance_id] = status
    with _lock:
        for cached in _cache.values():
            for amb in cached["data"]:
                if amb["id"] == ambulance_id:
                    amb["status"] = status
                    if lat is not None:
                        amb["latitude"] = lat
                    if lon is not None:
                        amb["longitude"] = lon


# Legacy: load_ambulances() without location (used by /api/ambulances route)
def load_ambulances(force=False):
    """Backward-compatible: load JSON directly."""
    try:
        with open(_json_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return _hardcoded_fallback()
