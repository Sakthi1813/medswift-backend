// ═══════════════════════════════════════════════════════════════
//  MedSwift – map.js   (Real-time ambulance markers)
// ═══════════════════════════════════════════════════════════════
let map = null, userMarker = null, ambulanceMarker = null,
    hospitalMarker = null, routePolyline = null,
    hospitalMarkers = [], nearbyAmbulanceMarkers = {};

const ICONS = {
  user: L.divIcon({
    className: "",
    html: '<div style="width:18px;height:18px;background:#6366f1;border-radius:50%;border:3px solid #fff;box-shadow:0 0 0 3px #6366f1,0 4px 12px rgba(99,102,241,0.5);"></div>',
    iconSize: [18,18], iconAnchor: [9,9]
  }),
  ambulance: L.divIcon({
    className: "",
    html: '<div style="width:30px;height:30px;background:linear-gradient(135deg,#f43f5e,#e11d48);border-radius:8px;display:flex;align-items:center;justify-content:center;color:#fff;font-size:16px;box-shadow:0 4px 14px rgba(244,63,94,0.55);border:2px solid #fff;">🚑</div>',
    iconSize: [30,30], iconAnchor: [15,15]
  }),
  ambulanceBusy: L.divIcon({
    className: "",
    html: '<div style="width:26px;height:26px;background:#94a3b8;border-radius:8px;display:flex;align-items:center;justify-content:center;color:#fff;font-size:13px;box-shadow:0 2px 8px rgba(0,0,0,0.25);border:2px solid #fff;opacity:0.75;">🚑</div>',
    iconSize: [26,26], iconAnchor: [13,13]
  }),
  hospital: L.divIcon({
    className: "",
    html: '<div style="width:28px;height:28px;background:linear-gradient(135deg,#10b981,#059669);border-radius:50%;display:flex;align-items:center;justify-content:center;color:#fff;font-size:13px;font-weight:700;box-shadow:0 4px 12px rgba(16,185,129,0.5);border:2px solid #fff;">H</div>',
    iconSize: [28,28], iconAnchor: [14,14]
  }),
  hospitalSmall: L.divIcon({
    className: "",
    html: '<div style="width:14px;height:14px;background:#10b981;border-radius:50%;border:2px solid #fff;box-shadow:0 2px 6px rgba(16,185,129,0.4);"></div>',
    iconSize: [14,14], iconAnchor: [7,7]
  })
};

function initMap(lat, lon) {
  if (map) { map.setView([lat, lon], 13); return; }
  map = L.map("map", { zoomControl: true }).setView([lat, lon], 13);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors", maxZoom: 19
  }).addTo(map);
}

function setUserMarker(lat, lon) {
  if (!map) initMap(lat, lon);
  if (userMarker) map.removeLayer(userMarker);
  userMarker = L.marker([lat, lon], { icon: ICONS.user }).addTo(map)
    .bindPopup("<strong>Your Location</strong>");
  map.setView([lat, lon], 14);
}

function setAmbulanceMarker(lat, lon, label) {
  if (ambulanceMarker) map.removeLayer(ambulanceMarker);
  ambulanceMarker = L.marker([lat, lon], { icon: ICONS.ambulance }).addTo(map)
    .bindPopup(`<strong>Your Ambulance</strong><br/>${label || ""}`);
}

function setHospitalMarker(lat, lon, name) {
  if (hospitalMarker) map.removeLayer(hospitalMarker);
  hospitalMarker = L.marker([lat, lon], { icon: ICONS.hospital }).addTo(map)
    .bindPopup(`<strong>${name}</strong>`);
}

function showNearestHospitals(hospitals) {
  hospitalMarkers.forEach(m => map.removeLayer(m));
  hospitalMarkers = [];
  hospitals.forEach((h, i) => {
    const icon = i === 0 ? ICONS.hospital : ICONS.hospitalSmall;
    const popup = `
      <strong>${h.name}</strong><br/>
      ${h.speciality ? `<em style="color:#10b981;font-size:11px;">${h.speciality}</em><br/>` : ""}
      ${h.address   ? `<span style="font-size:11px;">${h.address}</span><br/>` : ""}
      ${h.phone     ? `📞 <span style="font-size:11px;">${h.phone}</span><br/>` : ""}
      <small style="color:#6366f1;"><strong>${h.distance_km} km</strong> &bull; ETA <strong>${h.eta_minutes} min</strong></small>`;
    const m = L.marker([h.latitude, h.longitude], { icon }).addTo(map).bindPopup(popup);
    hospitalMarkers.push(m);
  });
}

// ── NEW: Show nearby ambulances on map ────────────────────────
function showNearbyAmbulancesOnMap(ambulances) {
  if (!map) return;

  const incoming = {};
  ambulances.forEach(a => { incoming[a.id] = a; });

  // Remove markers that are no longer in the list
  Object.keys(nearbyAmbulanceMarkers).forEach(id => {
    if (!incoming[id]) {
      map.removeLayer(nearbyAmbulanceMarkers[id]);
      delete nearbyAmbulanceMarkers[id];
    }
  });

  // Add / update markers
  ambulances.forEach(a => {
    const lat = parseFloat(a.latitude);
    const lon = parseFloat(a.longitude);
    const icon = a.status === "available" ? ICONS.ambulance : ICONS.ambulanceBusy;
    const popupHtml = `
      <strong>${a.driver_name}</strong><br/>
      ${a.vehicle_number}<br/>
      <span style="color:${a.status==="available"?"#10b981":"#94a3b8"};font-weight:600;">
        ${a.status === "available" ? "✅ Available" : "🔴 Busy"}
      </span><br/>
      📍 ${a.distance_km} km &bull; ETA ~${a.eta_minutes} min
      ${a.hospital ? `<br/>🏥 ${a.hospital}` : ""}`;

    if (nearbyAmbulanceMarkers[a.id]) {
      nearbyAmbulanceMarkers[a.id].setLatLng([lat, lon])
        .setIcon(icon)
        .setPopupContent(popupHtml);
    } else {
      nearbyAmbulanceMarkers[a.id] = L.marker([lat, lon], { icon })
        .addTo(map).bindPopup(popupHtml);
    }
  });
}

function drawRoute(coords) {
  if (routePolyline) map.removeLayer(routePolyline);
  if (!coords || coords.length < 2) return;
  routePolyline = L.polyline(coords, {
    color: "#6366f1", weight: 4, opacity: 0.9, dashArray: "8, 5"
  }).addTo(map);
  map.fitBounds(routePolyline.getBounds(), { padding: [50, 50] });
}

function updateAmbulancePosition(lat, lon) {
  if (ambulanceMarker) ambulanceMarker.setLatLng([lat, lon]);
}

function clearRoute() {
  if (routePolyline) { map.removeLayer(routePolyline); routePolyline = null; }
  if (ambulanceMarker) { map.removeLayer(ambulanceMarker); ambulanceMarker = null; }
  if (hospitalMarker) { map.removeLayer(hospitalMarker); hospitalMarker = null; }
  hospitalMarkers.forEach(m => map.removeLayer(m)); hospitalMarkers = [];
}
