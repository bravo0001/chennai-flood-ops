// Relative path (Kyunki Cloud Run par hi frontend aur backend dono hain)
const API_BASE = "";

// 1. Crystal-Clear, Watermark-Free Basemaps
const satTile = L.tileLayer('https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', {
  maxZoom: 20,
  attribution: '&copy; Google Maps'
});

const streetTile = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '&copy; OpenStreetMap contributors'
});

const liveRadarGroup = L.layerGroup();

// Initialize Map with zoomControl moved to bottom-right
const map = L.map('map', {
  center: [13.0450, 80.2300],
  zoom: 12,
  minZoom: 9,
  maxZoom: 20,
  layers: [satTile, liveRadarGroup],
  zoomControl: false,
  preferCanvas: true
});

// Add Zoom Control at Bottom-Right (Shifted right above telemetry dashboard)
L.control.zoom({ position: 'bottomright' }).addTo(map);

let cityRoadsGroup = L.featureGroup().addTo(map);
let navigationGroup = L.featureGroup().addTo(map);

// 1. Red Cluster Group for Hospitals
let hospitalClusterGroup = L.markerClusterGroup({
  maxClusterRadius: 40,
  iconCreateFunction: function(cluster) {
    return L.divIcon({
      html: `<div><span>${cluster.getChildCount()}</span></div>`,
      className: 'marker-cluster hospital-cluster',
      iconSize: L.point(40, 40)
    });
  }
}).addTo(map);

// 2. Yellow Cluster Group for Municipal Manholes & Inlets
let manholeClusterGroup = L.markerClusterGroup({
  maxClusterRadius: 35,
  iconCreateFunction: function(cluster) {
    return L.divIcon({
      html: `<div><span>${cluster.getChildCount()}</span></div>`,
      className: 'marker-cluster mh-cluster',
      iconSize: L.point(40, 40)
    });
  }
}).addTo(map);

const baseMaps = {
  "<span style='color:#4ade80;'>🛰️ Satellite</span>": satTile,
  "<span style='color:#38bdf8;'>🗺️ Street Map</span>": streetTile
};

const overlayMaps = {
  "<b style='color:#22c55e;'>🛣️ Road Simulation</b>": cityRoadsGroup,
  "<b style='color:#38bdf8;'>🌧️ Live Clouds / Radar</b>": liveRadarGroup,
  "<b style='color:#ef4444;'>🏥 Hospitals & Trauma</b>": hospitalClusterGroup,
  "<b style='color:#eab308;'>🕳️ Municipal Manholes & Inlets</b>": manholeClusterGroup,
  "<b style='color:#00e5ff;'>🚑 Emergency Route</b>": navigationGroup
};

L.control.layers(baseMaps, overlayMaps, { position: 'topright', collapsed: true }).addTo(map);

// 2. Real-Time Dynamic RainViewer Doppler Radar
function loadLiveRainViewerRadar() {
  fetch('https://api.rainviewer.com/public/weather-maps.json')
    .then(r => r.json())
    .then(data => {
      liveRadarGroup.clearLayers();
      const host = data.host;
      const frames = (data.radar && data.radar.past) ? data.radar.past : [];
      if (frames.length > 0) {
        const latestPath = frames[frames.length - 1].path;
        const radarTileUrl = `${host}${latestPath}/256/{z}/{x}/{y}/2/1_1.png`;
        const radarLayer = L.tileLayer(radarTileUrl, { opacity: 0.70, zIndex: 500 });
        liveRadarGroup.addLayer(radarLayer);
      }
    })
    .catch(e => console.error("RainViewer Radar error:", e));
}
loadLiveRainViewerRadar();
setInterval(loadLiveRainViewerRadar, 300000);

let rawRoadsData = null;
let currentRoadLayer = null;
let hoveredLayer = null;
let startCoords = null;
let endCoords = null;
let startMarker = null;
let endMarker = null;

document.getElementById('input-rain').oninput = e => document.getElementById('val-rain').innerText = `${e.target.value} mm/hr`;
document.getElementById('input-duration').oninput = e => document.getElementById('val-duration').innerText = `${e.target.value} min`;

// 3. Fetch Roads from Backend API
fetch('/api/roads')
  .then(res => res.json())
  .then(geojsonData => {
    rawRoadsData = geojsonData;
    triggerSimulation();
  })
  .catch(err => console.error("Roads fetch error:", err));

// 4. Fetch Hospitals from Backend API
fetch('/api/hospitals')
  .then(res => res.json())
  .then(data => {
    const hLayer = L.geoJSON(data, {
      pointToLayer: (feat, latlng) => L.marker(latlng, {
        icon: L.divIcon({ className: 'hospital-marker', html: '+', iconSize: [18, 18], iconAnchor: [9, 9] })
      }),
      onEachFeature: (feat, layer) => {
        const p = feat.properties;
        layer.bindPopup(`
          <div style="font-size:12px; color:#1e293b;">
            <b style="color:#ef4444;">${p.name}</b><br>
            <b>Type:</b> ${(p.type || 'Clinic').toUpperCase()}<br>
            <button onclick="setHospitalDestination(${feat.geometry.coordinates[1]}, ${feat.geometry.coordinates[0]}, '${p.name.replace(/'/g, "\\'")}')" 
              style="margin-top:6px; background:#0284c7; color:white; border:none; padding:4px 8px; border-radius:4px; cursor:pointer;">
              Set Destination
            </button>
          </div>
        `);
      }
    });
    hospitalClusterGroup.addLayer(hLayer);
  })
  .catch(err => console.error("Hospitals error:", err));

// 5. Hydrology Simulation with Street Hover Telemetry & Water Clearance
function triggerSimulation() {
  if (!rawRoadsData) return;

  const rainIntensity = parseFloat(document.getElementById('input-rain').value);
  const durationMin = parseFloat(document.getElementById('input-duration').value);
  const drainFactor = parseFloat(document.getElementById('input-drainage').value);

  if (currentRoadLayer) {
    cityRoadsGroup.removeLayer(currentRoadLayer);
  }

  currentRoadLayer = L.geoJSON(rawRoadsData, {
    style: function(feature) {
      const p = feature.properties;
      const elev = Math.max(1.0, parseFloat(p.elevation_msl || 4.0));
      const runoffCoeff = parseFloat(p.runoff_coeff || 0.75);

      const roadArea = 1200.0;
      const rainRateLps = (rainIntensity / 3600.0) * roadArea;
      const runoffRateLps = rainRateLps * runoffCoeff;

      const dia = parseInt(p.pipe_dia_mm || 350);
      let baseIntake = 6.0;
      if (dia >= 1200) baseIntake = 32.0;
      else if (dia >= 900) baseIntake = 20.0;
      else if (dia >= 600) baseIntake = 12.0;

      const gravityMult = elev < 3.5 ? 0.40 : (elev < 6.5 ? 0.75 : 1.15);
      const drainRateLps = baseIntake * drainFactor * gravityMult;

      const netInflow = Math.max(0.0, runoffRateLps - drainRateLps);
      const accumulatedLiters = netInflow * (durationMin * 60.0);
      const poolingMult = 1.0 + (1.8 / Math.pow(elev, 0.65));
      const totalPooledLiters = accumulatedLiters * poolingMult;
      const depthCM = Math.round(((totalPooledLiters) / roadArea) * 0.1 * 10) / 10;

      // Clearance Time Computation
      let clearMins = 0;
      if (depthCM > 0 && drainRateLps > 0) {
        clearMins = Math.round((totalPooledLiters / drainRateLps) / 60.0);
      }

      p._liveDepth = depthCM;
      p._effectiveLps = Math.round(drainRateLps * 10) / 10;
      p._clearanceMins = clearMins;

      if (depthCM > 7.0) {
        return { color: "#ef4444", weight: 2.5, opacity: 0.9 };
      } else if (depthCM >= 1.5) {
        return { color: "#f59e0b", weight: 1.8, opacity: 0.8 };
      } else {
        return { color: "#22c55e", weight: 1.2, opacity: 0.5 };
      }
    },
    onEachFeature: function(feature, layer) {
      layer.on('mouseover', function(e) {
        if (hoveredLayer) currentRoadLayer.resetStyle(hoveredLayer);
        hoveredLayer = e.target;
        hoveredLayer.setStyle({ weight: 5, color: "#38bdf8", opacity: 1.0 });

        const p = feature.properties;
        const nameElem = document.getElementById('disp-name');
        const elevElem = document.getElementById('disp-elev');
        const dirElem = document.getElementById('disp-dir');
        const surfElem = document.getElementById('disp-surface');
        const capElem = document.getElementById('disp-capacity');
        const depthElem = document.getElementById('disp-depth');
        const clearElem = document.getElementById('disp-clearance');
        const sElem = document.getElementById('disp-status');

        if (nameElem) nameElem.innerText = p.name || p.highway || "City Street";
        if (elevElem) elevElem.innerText = `${p.elevation_msl || '4.0'} m MSL`;
        if (dirElem) dirElem.innerText = p.flow_direction || "Drainward";
        if (surfElem) surfElem.innerText = p.surface_material || "Asphalt / Semi-Paved";
        if (capElem) capElem.innerText = `${p._effectiveLps || 6} L/sec`;
        if (depthElem) depthElem.innerText = `${p._liveDepth} cm`;

        // Telemetry Clearance Time Display
        if (clearElem) {
          if (p._liveDepth <= 0.2) {
            clearElem.innerHTML = `<span style="color:#4ade80;">Immediate (Free Flow)</span>`;
          } else if (p._effectiveLps <= 0.1) {
            clearElem.innerHTML = `<span style="color:#ef4444;">Stagnant (Zero Drain)</span>`;
          } else if (p._clearanceMins > 120) {
            const hrs = (p._clearanceMins / 60).toFixed(1);
            clearElem.innerHTML = `<span style="color:#ef4444;">~${hrs} hrs (Severe Silt)</span>`;
          } else {
            clearElem.innerHTML = `<span style="color:#38bdf8;">~${p._clearanceMins} mins</span>`;
          }
        }

        if (sElem) {
          if (p._liveDepth > 7.0) {
            sElem.innerHTML = `<span class="status-badge flooded">Severe Flooding (>7cm)</span>`;
          } else if (p._liveDepth >= 1.5) {
            sElem.innerHTML = `<span class="status-badge slow-drain">Waterlogged (Caution)</span>`;
          } else {
            sElem.innerHTML = `<span class="status-badge drained">Safe / Passable</span>`;
          }
        }
      });
    }
  });

  cityRoadsGroup.addLayer(currentRoadLayer);
  if (startCoords && endCoords) requestSafeRoute();
}

// 6. Autocomplete Locality Search
setupSearch('input-start', 'results-start', (lat, lon, label) => {
  startCoords = [lat, lon];
  document.getElementById('input-start').value = label;
  if (startMarker) navigationGroup.removeLayer(startMarker);
  startMarker = L.marker(startCoords).bindPopup(`Start: ${label}`).openPopup();
  navigationGroup.addLayer(startMarker);
  map.setView(startCoords, 14);
});

setupSearch('input-end', 'results-end', (lat, lon, label) => {
  endCoords = [lat, lon];
  document.getElementById('input-end').value = label;
  if (endMarker) navigationGroup.removeLayer(endMarker);
  endMarker = L.marker(endCoords).bindPopup(`Destination: ${label}`).openPopup();
  navigationGroup.addLayer(endMarker);
  map.setView(endCoords, 14);
});

function setupSearch(inputId, resId, onSelect) {
  const input = document.getElementById(inputId);
  const res = document.getElementById(resId);
  let timeout = null;

  input.addEventListener('input', () => {
    clearTimeout(timeout);
    const q = input.value.trim();
    if (q.length < 3) { res.style.display = 'none'; return; }

    timeout = setTimeout(() => {
      fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(q + ' Chennai')}&limit=5`)
        .then(r => r.json())
        .then(items => {
          res.innerHTML = '';
          if (!items.length) { res.style.display = 'none'; return; }
          items.forEach(it => {
            const d = document.createElement('div');
            d.className = 'dropdown-item';
            d.innerText = it.display_name.split(',').slice(0, 3).join(',');
            d.onclick = () => {
              onSelect(parseFloat(it.lat), parseFloat(it.lon), d.innerText);
              res.style.display = 'none';
            };
            res.appendChild(d);
          });
          res.style.display = 'block';
        })
        .catch(err => console.error("Search fetch error:", err));
    }, 300);
  });
}

window.setHospitalDestination = function(lat, lon, name) {
  endCoords = [lat, lon];
  document.getElementById('input-end').value = name;
  if (endMarker) navigationGroup.removeLayer(endMarker);
  endMarker = L.marker(endCoords).bindPopup(`Hospital: ${name}`).openPopup();
  navigationGroup.addLayer(endMarker);
  if (startCoords) requestSafeRoute();
};

// 7. Dual Route Computation (Dashed Normal vs Solid Safe)
function requestSafeRoute() {
  if (!startCoords || !endCoords) {
    alert("Please enter both Start Location and Destination!");
    return;
  }

  document.querySelectorAll('.marker-cluster').forEach(el => el.style.opacity = '0.35');

  const payload = {
    start_lat: startCoords[0],
    start_lon: startCoords[1],
    end_lat: endCoords[0],
    end_lon: endCoords[1],
    rain_intensity: parseFloat(document.getElementById('input-rain').value),
    duration_min: parseFloat(document.getElementById('input-duration').value),
    drain_factor: parseFloat(document.getElementById('input-drainage').value)
  };

  fetch('/api/route', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  })
  .then(res => res.json())
  .then(data => {
    navigationGroup.eachLayer(l => {
      if (l instanceof L.Polyline && !(l instanceof L.Polygon)) navigationGroup.removeLayer(l);
    });

    const summary = document.getElementById('route-summary');
    summary.style.display = 'block';

    if (data.status !== 'success') {
      summary.innerHTML = `<b style="color:#ef4444;">Route Notice:</b> ${data.message || 'No safe path available'}`;
      return;
    }

    // 1. Flood-Safe Route (Solid Light Blue)
    const safePath = data.safe_route.coordinates.map(c => [c[1], c[0]]);
    const safePoly = L.polyline(safePath, {
      color: "#00e5ff",
      weight: 6,
      opacity: 0.95
    }).addTo(navigationGroup);
    safePoly.bindTooltip("Flood-Safe High Elevation Route (Solid)", { sticky: true });

    // 2. Normal Route (Dashed Coral/Red)
    const normalPath = data.normal_route.coordinates.map(c => [c[1], c[0]]);
    const normalPoly = L.polyline(normalPath, {
      color: "#ff4757",
      weight: 3.5,
      dashArray: "6, 8",
      opacity: 0.95
    }).addTo(navigationGroup);
    normalPoly.bindTooltip("Normal Shortest Route (Dashed)", { sticky: true });

    map.fitBounds(safePoly.getBounds(), { padding: [50, 50] });

    const n = data.normal_route;
    const s = data.safe_route;
    summary.innerHTML = `
      <div style="margin-bottom:6px;">
        <span style="color:#ff4757; font-weight:bold;">--- Normal Route:</span> ${n.distance_km} km (~${n.est_time_min} mins)<br>
        <small style="color:${n.flooded_segments > 0 ? '#ef4444' : '#4ade80'};">
          ${n.flooded_segments > 0 ? `⚠️ Crosses ${n.flooded_segments} inundated road segments` : '✓ Clear'}
        </small>
      </div>
      <div style="border-top:1px solid rgba(255,255,255,0.1); padding-top:6px;">
        <span style="color:#00e5ff; font-weight:bold;">━ Flood-Safe Route:</span> ${s.distance_km} km (~${s.est_time_min} mins)<br>
        <small style="color:#4ade80;">✓ Steered via high-elevation, unflooded roads</small>
      </div>
    `;
  })
  .catch(err => console.error("Routing error:", err));
}

function clearNavigation() {
  document.getElementById('input-start').value = '';
  document.getElementById('input-end').value = '';
  document.getElementById('route-summary').style.display = 'none';
  startCoords = null;
  endCoords = null;
  navigationGroup.clearLayers();
  document.querySelectorAll('.marker-cluster').forEach(el => el.style.opacity = '1.0');
}

// 8. Live Weather Engine
let liveRainRate = 12.4;
let autoSyncWeather = false;

function fetchLiveWeather() {
  fetch('/api/live-weather')
    .then(res => res.json())
    .then(data => {
      document.getElementById('wt-temp').innerText = `${Math.round(data.temp)}°C`;
      document.getElementById('wt-rain').innerText = `${data.rain_mm} mm/hr`;
      document.getElementById('wt-wind').innerText = `${data.wind_speed} km/h`;
      document.getElementById('wt-humidity').innerText = `${data.humidity}%`;
      
      const deg = data.wind_dir;
      const dirs = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
      const compass = dirs[Math.round(deg / 45) % 8];
      document.getElementById('wt-dir').innerText = `${compass} (${deg}°)`;
      document.getElementById('wt-condition').innerText = data.rain_mm > 0 ? "Active Precipitation Cell" : "Overcast / Dry";
      
      const now = new Date();
      document.getElementById('wt-time').innerText = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

      liveRainRate = data.rain_mm;

      if (autoSyncWeather) applyLiveRainToSimulation();
    })
    .catch(err => console.error("Weather update err:", err));
}

function applyLiveRainToSimulation() {
  const slider = document.getElementById('input-rain');
  slider.value = Math.min(150, Math.max(5, Math.round(liveRainRate)));
  document.getElementById('val-rain').innerText = `${slider.value} mm/hr`;
  triggerSimulation();
}

window.toggleLiveSync = function(isEnabled) {
  autoSyncWeather = isEnabled;
  if (isEnabled) applyLiveRainToSimulation();
};

fetchLiveWeather();
setInterval(fetchLiveWeather, 180000);

// 9. Municipal Manhole Engine (Yellow Operational, Black Blocked)
let currentSelectedMh = null;

function loadManholesData() {
  fetch('/api/manholes')
    .then(r => r.json())
    .then(data => {
      manholeClusterGroup.clearLayers();
      const layer = L.geoJSON(data, {
        pointToLayer: (feat, latlng) => {
          const isBlocked = feat.properties.status === "BLOCKED";
          // Operational = Yellow (.mh-clean), Reported/Blocked = Black (.mh-blocked)
          const iconClass = isBlocked ? "manhole-icon mh-blocked" : "manhole-icon mh-clean";
          return L.marker(latlng, {
            icon: L.divIcon({ className: iconClass, iconSize: [12, 12], iconAnchor: [6, 6] })
          });
        },
        onEachFeature: (feat, layer) => {
          layer.on('click', () => showManholeCard(feat.properties));
        }
      });
      manholeClusterGroup.addLayer(layer);
    })
    .catch(e => console.error("Manholes fetch error:", e));
}
loadManholesData();

function showManholeCard(props) {
  currentSelectedMh = props;
  const card = document.getElementById('manhole-incident-card');
  card.style.display = 'block';

  document.getElementById('card-mh-id').innerText = props.id;
  document.getElementById('card-mh-street').innerText = `${props.street} (${props.elevation_msl}m MSL)`;

  const isBlocked = props.status === "BLOCKED";
  const badge = document.getElementById('card-status-badge');
  badge.innerHTML = isBlocked
    ? `<span class="status-badge" style="background:#000; color:#facc15; border:1px solid #facc15;">⚫ CHOKED / BLOCKED (ALERT SENT)</span>`
    : `<span class="status-badge slow-drain">🟡 OPERATIONAL CHAMBER (YELLOW)</span>`;

  if (isBlocked) {
    document.getElementById('card-report-form').style.display = 'none';
    document.getElementById('card-view-details').style.display = 'block';
    document.getElementById('card-view-notes').innerText = `Report: "${props.report_notes || 'Silt blockage'}" at ${props.last_reported}`;
    const imgBox = document.getElementById('card-view-img');
    imgBox.innerHTML = props.image_url 
      ? `<img src="${props.image_url}" style="max-width:100%; border-radius:5px; max-height:100px; object-fit:cover;" />` 
      : `<small style="color:#94a3b8; font-size:10px;">No photo attached</small>`;
  } else {
    document.getElementById('card-report-form').style.display = 'block';
    document.getElementById('card-view-details').style.display = 'none';
    document.getElementById('card-notes').value = '';
    document.getElementById('card-file-input').value = '';
  }

  card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function closeManholeCard() {
  document.getElementById('manhole-incident-card').style.display = 'none';
  currentSelectedMh = null;
}

function submitManholeReport() {
  if (!currentSelectedMh) return;
  const notes = document.getElementById('card-notes').value || "Choked with plastic waste & silt";
  const fileInput = document.getElementById('card-file-input');

  const sendPayload = (base64Img) => {
    fetch('/api/manhole/report', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: currentSelectedMh.id, notes: notes, image_base64: base64Img })
    })
    .then(r => r.json())
    .then(() => {
      alert(`Priority alert sent to Greater Chennai Corporation for ${currentSelectedMh.id}!`);
      closeManholeCard();
      loadManholesData(); // Changes marker from Yellow to Black
    });
  };

  if (fileInput.files && fileInput.files[0]) {
    const reader = new FileReader();
    reader.onload = (e) => sendPayload(e.target.result);
    reader.readAsDataURL(fileInput.files[0]);
  } else {
    sendPayload("");
  }
}

function resolveCurrentManhole() {
  if (!currentSelectedMh) return;
  fetch('/api/manhole/resolve', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id: currentSelectedMh.id })
  })
  .then(r => r.json())
  .then(() => {
    alert(`Chamber ${currentSelectedMh.id} resolved and restored by GCC!`);
    closeManholeCard();
    loadManholesData(); // Changes marker back to Yellow
  });
}
