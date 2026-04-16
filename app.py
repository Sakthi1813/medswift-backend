from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
import os
import sys
sys.modules['google._upb._message'] = None
import uuid
import json
import threading
import time
from datetime import datetime

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "medswift_secret_2024")
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*")

from services.hospital_finder import find_nearest_hospitals
from services.ambulance_dispatcher import (
    find_nearest_ambulance,
    find_nearby_ambulances,
    update_ambulance_status,
    load_ambulances,
    load_ambulances_for,
)
from services.route_service import get_full_route
from services.email_service import send_booking_confirmation, send_hospital_alert
from firebase_config import get_firebase_web_config

bookings_store = {}

# ──────────────────────────────────────────────
# Page routes (unchanged)
# ──────────────────────────────────────────────

@app.route("/")
def landing():
    return render_template("landing.html")

@app.route("/login")
def login():
    return render_template("login.html", firebase_config=get_firebase_web_config())

@app.route("/signup")
def signup():
    return render_template("signup.html", firebase_config=get_firebase_web_config())

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html", firebase_config=get_firebase_web_config())

@app.route("/api/firebase-config")
def firebase_config_endpoint():
    return jsonify(get_firebase_web_config())

# ──────────────────────────────────────────────
# Hospital / route / booking endpoints (unchanged)
# ──────────────────────────────────────────────

@app.route("/api/find-hospitals", methods=["POST"])
def api_find_hospitals():
    """
    PRIMARY: Ask Gemini to generate hospitals near the user's GPS coords.
    FALLBACK: Repositioned CSV data if Gemini is unavailable.
    Returns hospitals sorted closest-first, with optional emergency type filter.
    """
    data = request.get_json()
    lat = float(data.get("latitude", 28.6139))
    lon = float(data.get("longitude", 77.2090))
    emergency_type = data.get("emergency_type", "general")
    count = int(data.get("count", 5))
    hospitals = find_nearest_hospitals(lat, lon, count, emergency_type)
    return jsonify({
        "success": True,
        "hospitals": hospitals,
        "total": len(hospitals),
        "timestamp": datetime.now().isoformat(),
        "source": "gemini"
    })

@app.route("/api/find-ambulance", methods=["POST"])
def api_find_ambulance():
    data = request.get_json()
    lat = float(data.get("latitude", 28.6139))
    lon = float(data.get("longitude", 77.2090))
    ambulance = find_nearest_ambulance(lat, lon)
    if ambulance:
        return jsonify({"success": True, "ambulance": ambulance})
    return jsonify({"success": False, "error": "No ambulances available"}), 503

# ──────────────────────────────────────────────
# NEW: Real-time nearby ambulances endpoint
# ──────────────────────────────────────────────

@app.route("/api/nearby-ambulances", methods=["POST"])
def api_nearby_ambulances():
    """
    PRIMARY: Ask Gemini to generate ambulances near the user's GPS coords.
    FALLBACK: Repositioned JSON data if Gemini is unavailable.
    Returns ambulances within 5 km, sorted closest-first.
    """
    data = request.get_json()
    lat = float(data.get("latitude", 28.6139))
    lon = float(data.get("longitude", 77.2090))
    radius = float(data.get("radius_km", 5.0))
    nearby = find_nearby_ambulances(lat, lon, radius_km=radius)
    return jsonify({
        "success": True,
        "ambulances": nearby,
        "total": len(nearby),
        "available": sum(1 for a in nearby if a["status"] == "available"),
        "timestamp": datetime.now().isoformat(),
        "source": "gemini"
    })

@app.route("/api/get-route", methods=["POST"])
def api_get_route():
    data = request.get_json()
    try:
        route = get_full_route(
            float(data["ambulance_lat"]), float(data["ambulance_lon"]),
            float(data["user_lat"]), float(data["user_lon"]),
            float(data["hospital_lat"]), float(data["hospital_lon"])
        )
        return jsonify({"success": True, "route": route})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/create-booking", methods=["POST"])
def api_create_booking():
    data = request.get_json()
    booking_id = "MS" + str(uuid.uuid4()).replace("-", "")[:8].upper()
    ambulance = data.get("ambulance")
    hospital = data.get("hospital")
    user_lat = float(data.get("user_lat", 28.6139))
    user_lon = float(data.get("user_lon", 77.2090))
    emergency_type = data.get("emergency_type", "General")
    user_email = data.get("user_email", "")
    user_name = data.get("user_name", "User")

    route_data = {}
    if ambulance and hospital:
        try:
            route_data = get_full_route(
                float(ambulance["latitude"]), float(ambulance["longitude"]),
                user_lat, user_lon,
                float(hospital["latitude"]), float(hospital["longitude"])
            )
        except Exception:
            pass

    eta = route_data.get("total_duration_min", ambulance.get("eta_minutes", 15) if ambulance else 15)

    booking = {
        "booking_id": booking_id,
        "timestamp": datetime.now().isoformat(),
        "status": "confirmed",
        "emergency_type": emergency_type,
        "user_name": user_name,
        "user_email": user_email,
        "user_location": {"lat": user_lat, "lon": user_lon},
        "ambulance": ambulance,
        "hospital": hospital,
        "eta_minutes": eta,
        "route": route_data
    }
    bookings_store[booking_id] = booking
    if ambulance:
        update_ambulance_status(ambulance["id"], "dispatched")
    if user_email:
        try:
            send_booking_confirmation(user_email, booking)
        except Exception as e:
            print(f"Email error: {e}")
    return jsonify({"success": True, "booking": booking})

@app.route("/api/booking/<booking_id>")
def api_get_booking(booking_id):
    booking = bookings_store.get(booking_id)
    if booking:
        return jsonify({"success": True, "booking": booking})
    return jsonify({"success": False, "error": "Booking not found"}), 404

@app.route("/api/track/<booking_id>")
def api_track(booking_id):
    booking = bookings_store.get(booking_id)
    if not booking:
        return jsonify({"success": False, "error": "Not found"}), 404
    ambulance = booking.get("ambulance", {})
    return jsonify({
        "success": True,
        "booking_id": booking_id,
        "status": booking.get("status", "confirmed"),
        "ambulance_lat": ambulance.get("latitude"),
        "ambulance_lon": ambulance.get("longitude"),
        "eta_minutes": booking.get("eta_minutes")
    })

@app.route("/api/ambulances")
def api_ambulances():
    return jsonify(load_ambulances())

# ──────────────────────────────────────────────
# WebSocket – real-time ambulance broadcasting
# ──────────────────────────────────────────────

_ws_subscribers = {}   # sid -> {"lat": ..., "lon": ...}
_broadcast_running = False

@socketio.on("connect")
def on_connect():
    print(f"[WS] Client connected: {request.sid}")

@socketio.on("disconnect")
def on_disconnect():
    _ws_subscribers.pop(request.sid, None)
    print(f"[WS] Client disconnected: {request.sid}")

@socketio.on("subscribe_ambulances")
def on_subscribe(data):
    """Client sends its lat/lon so server knows its area."""
    try:
        lat = float(data.get("lat", 28.6139))
        lon = float(data.get("lon", 77.2090))
        _ws_subscribers[request.sid] = {"lat": lat, "lon": lon}
        # Immediately push current data
        nearby = find_nearby_ambulances(lat, lon)
        emit("ambulance_update", {
            "ambulances": nearby,
            "available": sum(1 for a in nearby if a["status"] == "available"),
            "timestamp": datetime.now().isoformat()
        })
        _start_broadcast_loop()
    except Exception as e:
        print(f"[WS] Subscribe error: {e}")

@socketio.on("update_location")
def on_update_location(data):
    """Client can update its location (e.g. after movement)."""
    sid = request.sid
    if sid in _ws_subscribers:
        _ws_subscribers[sid]["lat"] = float(data.get("lat", _ws_subscribers[sid]["lat"]))
        _ws_subscribers[sid]["lon"] = float(data.get("lon", _ws_subscribers[sid]["lon"]))


def _start_broadcast_loop():
    global _broadcast_running
    if _broadcast_running:
        return
    _broadcast_running = True

    def loop():
        global _broadcast_running
        while True:
            time.sleep(6)           # broadcast every 6 seconds
            if not _ws_subscribers:
                _broadcast_running = False
                return
            try:
                # Refresh Gemini data per subscriber location
                for sid, info in list(_ws_subscribers.items()):
                    nearby = find_nearby_ambulances(info["lat"], info["lon"])
                    socketio.emit("ambulance_update", {
                        "ambulances": nearby,
                        "available": sum(1 for a in nearby if a["status"] == "available"),
                        "timestamp": datetime.now().isoformat(),
                        "source": "gemini"
                    }, to=sid)
            except Exception as e:
                print(f"[WS] Broadcast error: {e}")

    t = threading.Thread(target=loop, daemon=True)
    t.start()


if __name__ == "__main__":
    socketio.run(app, debug=True, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)
