// ═══════════════════════════════════════════════════════════════
//  MedSwift – main.js  (Real-time Nearby Ambulance Edition)
// ═══════════════════════════════════════════════════════════════
let currentUser  = null;
let userLat      = null;
let userLon      = null;
let selectedType = "General";
let currentBooking = null;
let trackingInterval = null;

// WebSocket connection
let socket = null;
let pollingInterval = null;          // fallback if WS unavailable
let selectedAmbulance = null;        // ambulance the user picked in the list

// ───────────────────────────────────────────
// Auth
// ───────────────────────────────────────────
auth.onAuthStateChanged(user => {
  if (!user) { window.location.href = "/login"; return; }
  currentUser = user;
  document.getElementById("user-display").textContent =
    user.displayName || user.email.split("@")[0];
  detectLocation();
});

function handleLogout() {
  disconnectSocket();
  auth.signOut().then(() => window.location.href = "/login");
}

// ───────────────────────────────────────────
// Status bar helpers
// ───────────────────────────────────────────
function showStatus(msg) {
  const b = document.getElementById("status-bar");
  b.style.display = "flex";
  document.getElementById("status-msg").textContent = msg;
}
function hideStatus() {
  document.getElementById("status-bar").style.display = "none";
}

// ───────────────────────────────────────────
// Geolocation
// ───────────────────────────────────────────
function detectLocation() {
  document.getElementById("loc-text").textContent = "Detecting location...";
  document.getElementById("coords-display").style.display = "none";
  showStatus("Acquiring GPS coordinates...");
  if (!navigator.geolocation) { setDefaultLocation(); return; }
  navigator.geolocation.getCurrentPosition(
    pos => {
      userLat = pos.coords.latitude;
      userLon = pos.coords.longitude;
      document.getElementById("loc-text").textContent = "Location detected";
      const cd = document.getElementById("coords-display");
      cd.textContent = `${userLat.toFixed(5)}, ${userLon.toFixed(5)}`;
      cd.style.display = "block";
      setUserMarker(userLat, userLon);
      loadNearestHospitals();
      loadNearbyAmbulances();          // ← NEW
      hideStatus();
    },
    () => {
      document.getElementById("loc-text").textContent =
        "Permission denied. Using Delhi default.";
      setDefaultLocation();
    },
    { enableHighAccuracy: true, timeout: 10000 }
  );
}

function setDefaultLocation() {
  userLat = 28.6139; userLon = 77.2090;
  setUserMarker(userLat, userLon);
  const cd = document.getElementById("coords-display");
  cd.textContent = `${userLat.toFixed(5)}, ${userLon.toFixed(5)} (default)`;
  cd.style.display = "block";
  loadNearestHospitals();
  loadNearbyAmbulances();              // ← NEW
  hideStatus();
}

function selectType(btn) {
  document.querySelectorAll(".etype-btn").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  selectedType = btn.dataset.type;
}

// ───────────────────────────────────────────
// Hospitals (unchanged)
// ───────────────────────────────────────────
async function loadNearestHospitals() {
  if (!userLat || !userLon) return;
  try {
    const res = await fetch("/api/find-hospitals", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ latitude: userLat, longitude: userLon, count: 5 })
    });
    const data = await res.json();
    if (data.success && data.hospitals.length) {
      showNearestHospitals(data.hospitals);
      renderHospitalList(data.hospitals);
      document.getElementById("hospitals-panel").style.display = "block";
    }
  } catch (e) { console.error("Hospital load error:", e); }
}

function renderHospitalList(hospitals) {
  document.getElementById("hospitals-list").innerHTML = hospitals.map((h, i) => `
    <div class="hospital-list-item">
      <div class="hospital-rank">${i + 1}</div>
      <div class="hospital-info">
        <div class="hospital-name">${h.name}</div>
        ${h.speciality ? `<div class="hospital-speciality">${h.speciality}</div>` : ""}
        <div class="hospital-meta">${h.distance_km} km &bull; ETA ${h.eta_minutes} min</div>
        <div class="hospital-addr">${h.address || h.city || ""}</div>
        ${h.phone ? `<div class="hospital-phone">${h.phone}</div>` : ""}
      </div>
    </div>`).join("");
}

// ═══════════════════════════════════════════════════════════════
//  REAL-TIME NEARBY AMBULANCES
// ═══════════════════════════════════════════════════════════════

// ── Fetch via HTTP (initial load + polling fallback) ──────────
async function loadNearbyAmbulances() {
  if (!userLat || !userLon) return;
  try {
    const res = await fetch("/api/nearby-ambulances", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ latitude: userLat, longitude: userLon, radius_km: 5 })
    });
    const data = await res.json();
    if (data.success) {
      renderNearbyAmbulances(data.ambulances, data.available);
      renderAmbulancesOnMap(data.ambulances);
    }
  } catch (e) { console.error("Nearby ambulances error:", e); }
  // Try to upgrade to WebSocket
  connectSocket();
}

// ── WebSocket connection ──────────────────────────────────────
function connectSocket() {
  if (socket && socket.connected) return;
  if (typeof io === "undefined") {
    // Socket.IO script not loaded — use polling
    startPolling();
    return;
  }
  socket = io();
  socket.on("connect", () => {
    console.log("[WS] Connected");
    stopPolling();
    socket.emit("subscribe_ambulances", { lat: userLat, lon: userLon });
  });
  socket.on("ambulance_update", data => {
    renderNearbyAmbulances(data.ambulances, data.available);
    renderAmbulancesOnMap(data.ambulances);
  });
  socket.on("disconnect", () => {
    console.warn("[WS] Disconnected — switching to polling");
    startPolling();
  });
  socket.on("connect_error", () => startPolling());
}

function disconnectSocket() {
  if (socket) { socket.disconnect(); socket = null; }
  stopPolling();
}

// ── Polling fallback (every 7 seconds) ───────────────────────
function startPolling() {
  if (pollingInterval) return;
  pollingInterval = setInterval(loadNearbyAmbulances, 7000);
}
function stopPolling() {
  if (pollingInterval) { clearInterval(pollingInterval); pollingInterval = null; }
}

// ── Render ambulance list UI ──────────────────────────────────
function renderNearbyAmbulances(ambulances, availableCount) {
  const panel = document.getElementById("nearby-ambulances-panel");
  const list  = document.getElementById("nearby-ambulances-list");
  const badge = document.getElementById("amb-available-badge");

  if (!panel) return;
  panel.style.display = "block";

  if (badge) badge.textContent = availableCount + " available";

  if (!ambulances || ambulances.length === 0) {
    list.innerHTML = `<div class="no-amb-msg">No ambulances found within 5 km.<br>
      <small>Showing all available units.</small></div>`;
    return;
  }

  list.innerHTML = ambulances.map(a => {
    const isAvail = a.status === "available";
    const selectedCls = (selectedAmbulance && selectedAmbulance.id === a.id) ? " amb-card-selected" : "";
    return `
    <div class="amb-card${selectedCls}" id="amb-card-${a.id}"
         onclick="selectAmbulanceCard(${JSON.stringify(a).replace(/"/g,"&quot;")})">
      <div class="amb-card-top">
        <span class="amb-type-badge amb-type-${a.type.toLowerCase()}">${a.type}</span>
        <span class="amb-status-dot ${isAvail ? "dot-avail" : "dot-busy"}"></span>
        <span class="amb-status-label">${isAvail ? "Available" : "Busy"}</span>
      </div>
      <div class="amb-driver">${a.driver_name}</div>
      <div class="amb-vehicle">${a.vehicle_number}</div>
      ${a.hospital ? `<div class="amb-hospital">🏥 ${a.hospital}</div>` : ""}
      <div class="amb-dist-row">
        <span class="amb-dist">${a.distance_km} km away</span>
        <span class="amb-eta">ETA ~${a.eta_minutes} min</span>
      </div>
      ${isAvail
        ? `<button class="btn-select-amb" onclick="event.stopPropagation();bookSelectedAmbulance(${JSON.stringify(a).replace(/"/g,"&quot;")})">
             Select &amp; Book
           </button>`
        : `<div class="amb-busy-note">Currently on a call</div>`}
    </div>`;
  }).join("");
}

// ── Render ambulances on map ──────────────────────────────────
function renderAmbulancesOnMap(ambulances) {
  if (typeof showNearbyAmbulancesOnMap === "function") {
    showNearbyAmbulancesOnMap(ambulances);
  }
}

// ── Select an ambulance card (highlight) ─────────────────────
function selectAmbulanceCard(amb) {
  selectedAmbulance = amb;
  document.querySelectorAll(".amb-card").forEach(c => c.classList.remove("amb-card-selected"));
  const el = document.getElementById("amb-card-" + amb.id);
  if (el) el.classList.add("amb-card-selected");
}

// ── Book a specific ambulance directly ───────────────────────
async function bookSelectedAmbulance(ambulance) {
  if (!userLat || !userLon) { alert("Location not detected. Please allow location access."); return; }
  selectedAmbulance = ambulance;
  await proceedToBooking(ambulance);
}

// ═══════════════════════════════════════════════════════════════
//  BOOKING FLOW
// ═══════════════════════════════════════════════════════════════

// Called from the "Book Emergency Transport" button (original flow)
async function initiateBooking() {
  if (!userLat || !userLon) { alert("Location not detected. Please allow location access."); return; }

  // If user already selected an ambulance from the list, use it
  if (selectedAmbulance && selectedAmbulance.status === "available") {
    await proceedToBooking(selectedAmbulance);
    return;
  }

  // Otherwise auto-pick nearest available
  const btn = document.getElementById("book-btn");
  btn.textContent = "Finding Ambulance..."; btn.disabled = true;
  showStatus("Finding nearest available ambulance...");
  try {
    const ambRes = await fetch("/api/find-ambulance", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ latitude: userLat, longitude: userLon })
    });
    const ambData = await ambRes.json();
    if (!ambData.success) throw new Error("No ambulances available nearby");
    await proceedToBooking(ambData.ambulance);
  } catch (e) {
    console.error("Booking error:", e);
    showStatus("Error: " + e.message);
    btn.textContent = "Book Emergency Transport"; btn.disabled = false;
  }
}

async function proceedToBooking(ambulance) {
  const btn = document.getElementById("book-btn");
  btn.textContent = "Processing..."; btn.disabled = true;
  showStatus("Finding best hospital...");
  try {
    const hospRes = await fetch("/api/find-hospitals", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        latitude: userLat, longitude: userLon, count: 1,
        emergency_type: selectedType
      })
    });
    const hospData = await hospRes.json();
    const hospital = hospData.hospitals[0];

    showStatus("Generating optimized route...");
    setAmbulanceMarker(ambulance.latitude, ambulance.longitude,
      `${ambulance.driver_name} – ${ambulance.vehicle_number}`);
    setHospitalMarker(hospital.latitude, hospital.longitude, hospital.name);

    const routeRes = await fetch("/api/get-route", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ambulance_lat: ambulance.latitude, ambulance_lon: ambulance.longitude,
        user_lat: userLat, user_lon: userLon,
        hospital_lat: hospital.latitude, hospital_lon: hospital.longitude
      })
    });
    const routeData = await routeRes.json();
    if (routeData.success && routeData.route.full_route)
      drawRoute(routeData.route.full_route);

    showStatus("Confirming booking...");
    const bookRes = await fetch("/api/create-booking", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ambulance, hospital,
        user_lat: userLat, user_lon: userLon,
        emergency_type: selectedType,
        user_email: currentUser.email,
        user_name: currentUser.displayName || currentUser.email
      })
    });
    const bookData = await bookRes.json();
    if (bookData.success) {
      currentBooking = bookData.booking;
      showBookingConfirmation(bookData.booking);
      startTracking(bookData.booking.booking_id, ambulance);
      stopPolling();
      disconnectSocket();
      hideStatus();
    }
  } catch (e) {
    console.error("Booking error:", e);
    showStatus("Error: " + e.message);
    btn.textContent = "Book Emergency Transport"; btn.disabled = false;
  }
}

// ───────────────────────────────────────────
// Post-booking UI (unchanged)
// ───────────────────────────────────────────
function showBookingConfirmation(booking) {
  document.getElementById("booking-panel").style.display    = "block";
  document.getElementById("hospitals-panel").style.display  = "none";
  document.getElementById("nearby-ambulances-panel").style.display = "none";
  document.getElementById("book-btn").style.display         = "none";
  document.getElementById("b-id").textContent      = booking.booking_id;
  document.getElementById("b-driver").textContent  = booking.ambulance.driver_name;
  document.getElementById("b-vehicle").textContent = booking.ambulance.vehicle_number;
  document.getElementById("b-eta").textContent     = Math.round(booking.eta_minutes) + " minutes";
  document.getElementById("assigned-hospital-card").innerHTML = `
    <div class="hospital-name">${booking.hospital.name}</div>
    <div class="hospital-addr">${booking.hospital.address || ""}</div>
    <div class="hospital-meta">${booking.hospital.distance_km || ""} km away</div>
    ${booking.hospital.phone ? `<div class="hospital-phone">${booking.hospital.phone}</div>` : ""}`;
}

function startTracking(bookingId, ambulance) {
  if (trackingInterval) clearInterval(trackingInterval);
  let step = 0;
  trackingInterval = setInterval(() => {
    step++;
    const jitter = () => (Math.random() - 0.5) * 0.005;
    updateAmbulancePosition(
      parseFloat(ambulance.latitude)  + jitter(),
      parseFloat(ambulance.longitude) + jitter()
    );
    if (step > 20) {
      clearInterval(trackingInterval);
      document.getElementById("b-status").textContent = "Arrived";
      document.getElementById("b-status").className  = "status-badge status-arrived";
    }
  }, 5000);
}
