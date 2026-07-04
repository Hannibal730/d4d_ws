/* =========================================================
   AEGIS ONE | Multi-UxV Web C2
   LIVE-DATA-FIRST MODE

   Default:
   - No mock equipment
   - No autonomous animation
   - UI stays empty until ROS / C2 publishes fleet state

   Optional UI demo mode:
   http://127.0.0.1:8080/?demo=1

   Expected normalized payload:
   /c2/fleet/state
   {
     "assets": [{
       "vehicle_id": "UAV_01",
       "vehicle_type": "UAV",
       "subtype": "Fixed-wing",
       "role": "Wide-area ISR",
       "battery_pct": 82.0,
       "link_quality": 0.93,
       "speed_mps": 23.4,
       "nav_confidence": 0.95,
       "assignable": true,
       "alert_level": "GREEN",
       "mission_state": "EXECUTING",
       "current_mission": "RECON_SECTOR_A",
       "lat": 37.8112,
       "lon": 128.0405,
       "alt_m": 420.0,
       "map_x": 548,
       "map_y": 171,
       "route": [[548,171],[520,212]]
     }]
   }

   ROSBridge endpoint:
   ws://127.0.0.1:9090
   ========================================================= */

const APP_CONFIG = {
  demoMode: new URLSearchParams(window.location.search).get("demo") === "1",
  rosBridgeUrl: "ws://127.0.0.1:9090",
  geoJsonPaths: [
    "./res/TL_SCCO_CTPRVN.json?v=20260704-noislands1",
    "../res/TL_SCCO_CTPRVN.json?v=20260704-noislands1",
    "../../res/TL_SCCO_CTPRVN.json?v=20260704-noislands1",
    "/res/TL_SCCO_CTPRVN.json?v=20260704-noislands1"
  ],
  topics: {
    fleetState: "/c2/fleet/state",
    alerts: "/c2/alerts",
    autopilotLog: "/c2/autopilot_log",
    missionLog: "/c2/mission_log",
    operatorCommand: "/c2/operator_command"
  }
};

const appState = {
  selectedId: null,
  activeFilter: "ALL",
  visibleLayers: {
    road: true,
    water: true,
    route: true
  },/*  */
  operationAreas: [],
  mapBbox: [124.7893155286271, 33.172610584346295, 130.96524575425667, 38.54255349620522],
  operatorActionCount: 0,
  rosConnected: false,
  assets: [],
  alerts: [],
  autopilotLogs: [],
  missionLogs: []
};

const refs = {
  clock: document.getElementById("clock"),
  systemStatus: document.getElementById("systemStatus"),
  connectRosButton: document.getElementById("connectRosButton"),
  demoModeBadge: document.getElementById("demoModeBadge"),
  geoJsonStatus: document.getElementById("geoJsonStatus"),
  equipmentList: document.getElementById("equipmentList"),
  assetTotal: document.getElementById("assetTotal"),
  assignableCount: document.getElementById("assignableCount"),
  operatorActionCount: document.getElementById("operatorActionCount"),
  alertCounter: document.getElementById("alertCounter"),
  alertList: document.getElementById("alertList"),
  selectedAssetTitle: document.getElementById("selectedAssetTitle"),
  selectedAssetSeverity: document.getElementById("selectedAssetSeverity"),
  stateData: document.getElementById("stateData"),
  missionDescription: document.getElementById("missionDescription"),
  cameraMode: document.getElementById("cameraMode"),
  cameraClock: document.getElementById("cameraClock"),
  cameraText: document.getElementById("cameraText"),
  cameraStatus: document.getElementById("cameraStatus"),
  autopilotLog: document.getElementById("autopilotLog"),
  missionLog: document.getElementById("missionLog"),
  clearAutoLogButton: document.getElementById("clearAutoLogButton"),
  operationAreaSelect: document.getElementById("operationAreaSelect"),
  geoJsonLayer: document.getElementById("geoJsonLayer"),
  routeLayer: document.getElementById("routeLayer"),
  vehicleLayer: document.getElementById("vehicleLayer"),
  mapStage: document.querySelector(".map-stage")
};

const SVG_NS = "http://www.w3.org/2000/svg";
const typeColor = {
  UAV: "#53d5e8",
  UGV: "#ffffff",
  USV: "#40aafb"
};

let rosSocket = null;

function removeLegacyMapOverlay() {
  document.getElementById("noAssetsOverlay")?.remove();
}

function getKstTime() {
  return new Intl.DateTimeFormat("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    timeZone: "Asia/Seoul"
  }).format(new Date());
}

function updateClock() {
  refs.clock.textContent = `${getKstTime()} KST`;
  refs.cameraClock.textContent = getKstTime();
}

function iconForType(type) {
  return { UAV: "✈", UGV: "▣", USV: "⛵" }[type] || "●";
}

function getSelectedAsset() {
  return appState.assets.find((asset) => asset.id === appState.selectedId) || null;
}

function ensureSelectedAsset() {
  if (!appState.selectedId && appState.assets.length) {
    appState.selectedId = appState.assets[0].id;
  }
  if (appState.selectedId && !appState.assets.some(a => a.id === appState.selectedId)) {
    appState.selectedId = appState.assets.length ? appState.assets[0].id : null;
  }
}

function setConnectionState(connected, detail = "") {
  appState.rosConnected = connected;
  const dot = document.querySelector(".live-dot");

  if (connected) {
    refs.systemStatus.textContent = "ROS CONNECTED · LIVE FLEET TELEMETRY";
    refs.connectRosButton.textContent = "Disconnect ROS";
    dot.classList.remove("connection-offline");
    dot.classList.add("connection-online");
  } else {
    refs.systemStatus.textContent = detail || "ROS OFFLINE · WAITING FOR FLEET STATE";
    refs.connectRosButton.textContent = "Connect ROS";
    dot.classList.remove("connection-online");
    dot.classList.add("connection-offline");
  }
}

function valueClass(value, warningThreshold, dangerThreshold) {
  if (value <= dangerThreshold) return "value-red";
  if (value <= warningThreshold) return "value-amber";
  return "value-green";
}

function renderEquipmentList() {
  refs.equipmentList.innerHTML = "";

  if (!appState.assets.length) {
    refs.equipmentList.innerHTML = `<div class="empty-state">No connected UxV assets.<br />Waiting for <code>/c2/fleet/state</code>.</div>`;
  } else {
    appState.assets.forEach((asset) => {
      const row = document.createElement("button");
      row.className = `equipment-row ${asset.id === appState.selectedId ? "selected" : ""}`;
      row.innerHTML = `
        <span class="platform-icon">${asset.icon || iconForType(asset.type)}</span>
        <span>
          <strong class="equipment-id">${asset.id.replace("_", "-")}</strong>
          <span class="equipment-role">${asset.subtype || asset.type} · ${asset.role || "Unassigned"}</span>
        </span>
        <span class="equipment-metrics">
          <span class="battery">${Math.round(asset.battery)}%</span>
          <span class="link">${Math.round(asset.link)}%</span>
        </span>
        <span class="alert-strip ${asset.alert || "GREEN"}"></span>
      `;
      row.addEventListener("click", () => {
        appState.selectedId = asset.id;
        renderAll();
      });
      refs.equipmentList.appendChild(row);
    });
  }

  refs.assetTotal.textContent = appState.assets.length;
  refs.assignableCount.textContent = `${appState.assets.filter((asset) => asset.assignable).length} / ${appState.assets.length}`;
  refs.operatorActionCount.textContent = appState.operatorActionCount;
}

function renderDetailPanel() {
  const asset = getSelectedAsset();

  if (!asset) {
    refs.selectedAssetTitle.textContent = "No asset selected";
    refs.selectedAssetSeverity.textContent = "WAITING";
    refs.selectedAssetSeverity.className = "severity-badge AMBER";
    refs.stateData.innerHTML = `
      <dt>Platform</dt><dd class="waiting-state">—</dd>
      <dt>Speed</dt><dd class="waiting-state">—</dd>
      <dt>Battery</dt><dd class="waiting-state">—</dd>
      <dt>Link quality</dt><dd class="waiting-state">—</dd>
      <dt>Nav confidence</dt><dd class="waiting-state">—</dd>
      <dt>Assignable</dt><dd class="waiting-state">—</dd>
      <dt>Coordinates</dt><dd class="waiting-state">—</dd>
      <dt>Mission state</dt><dd class="waiting-state">—</dd>
    `;
    refs.missionDescription.textContent = "Waiting for an asset selection from live fleet telemetry.";
    refs.cameraMode.textContent = "CAMERA / OFFLINE";
    refs.cameraText.textContent = "No live asset selected";
    refs.cameraStatus.textContent = "No video or telemetry source";
    return;
  }

  refs.selectedAssetTitle.textContent = `${asset.id.replace("_", "-")} · ${asset.type}`;
  refs.selectedAssetSeverity.textContent = asset.alert;
  refs.selectedAssetSeverity.className = `severity-badge ${asset.alert}`;

  refs.stateData.innerHTML = `
    <dt>Platform</dt><dd>${asset.subtype || asset.type}</dd>
    <dt>Speed</dt><dd>${asset.speed.toFixed(1)} m/s</dd>
    <dt>Battery</dt><dd class="${valueClass(asset.battery, 55, 35)}">${Math.round(asset.battery)}%</dd>
    <dt>Link quality</dt><dd class="${valueClass(asset.link, 80, 65)}">${Math.round(asset.link)}%</dd>
    <dt>Nav confidence</dt><dd>${asset.navConfidence}%</dd>
    <dt>Assignable</dt><dd class="${asset.assignable ? "value-green" : "value-red"}">${asset.assignable ? "ASSIGNABLE" : "NOT ASSIGNABLE"}</dd>
    <dt>Coordinates</dt><dd>${asset.lat.toFixed(4)}, ${asset.lon.toFixed(4)}</dd>
    <dt>Mission state</dt><dd>${asset.missionState}</dd>
  `;

  refs.missionDescription.textContent = asset.mission || "No mission assigned";
  refs.cameraMode.textContent = asset.cameraMode || "CAMERA / NO FEED";
  refs.cameraText.textContent = `${asset.id.replace("_", "-")} · ${asset.role || asset.type}`;
  refs.cameraStatus.textContent = asset.cameraStatus || "Telemetry synchronized";
}

function routePointsToText(points) {
  return (points || []).map(([x, y]) => `${x},${y}`).join(" ");
}

function getGeoJsonBbox(geoJson) {
  if (Array.isArray(geoJson.bbox) && geoJson.bbox.length >= 4) {
    return geoJson.bbox.slice(0, 4).map(Number);
  }

  const bbox = [Infinity, Infinity, -Infinity, -Infinity];
  const visitCoordinate = (coordinate) => {
    if (!Array.isArray(coordinate)) return;
    if (typeof coordinate[0] === "number" && typeof coordinate[1] === "number") {
      bbox[0] = Math.min(bbox[0], coordinate[0]);
      bbox[1] = Math.min(bbox[1], coordinate[1]);
      bbox[2] = Math.max(bbox[2], coordinate[0]);
      bbox[3] = Math.max(bbox[3], coordinate[1]);
      return;
    }
    coordinate.forEach(visitCoordinate);
  };

  (geoJson.features || []).forEach((feature) => visitCoordinate(feature.geometry?.coordinates));
  return bbox.every(Number.isFinite) ? bbox : null;
}

function getCoordinateBbox(coordinates) {
  const bbox = [Infinity, Infinity, -Infinity, -Infinity];
  const visitCoordinate = (coordinate) => {
    if (!Array.isArray(coordinate)) return;
    if (typeof coordinate[0] === "number" && typeof coordinate[1] === "number") {
      bbox[0] = Math.min(bbox[0], coordinate[0]);
      bbox[1] = Math.min(bbox[1], coordinate[1]);
      bbox[2] = Math.max(bbox[2], coordinate[0]);
      bbox[3] = Math.max(bbox[3], coordinate[1]);
      return;
    }
    coordinate.forEach(visitCoordinate);
  };
  visitCoordinate(coordinates);
  return bbox.every(Number.isFinite) ? bbox : null;
}

function extractOperationAreas(geoJson) {
  return (geoJson.features || [])
    .map((feature) => {
      const bbox = getCoordinateBbox(feature.geometry?.coordinates);
      if (!bbox) return null;

      const properties = feature.properties || {};
      const lon = (bbox[0] + bbox[2]) / 2;
      const lat = (bbox[1] + bbox[3]) / 2;
      const name = properties.CTP_KOR_NM || properties.CTP_ENG_NM || properties.name || "Operation area";
      const code = properties.CTPRVN_CD || name;

      return { code, name, lat, lon };
    })
    .filter(Boolean)
    .sort((a, b) => a.name.localeCompare(b.name, "ko"));
}

function renderOperationAreaOptions() {
  if (!refs.operationAreaSelect) return;

  if (!appState.operationAreas.length) {
    refs.operationAreaSelect.innerHTML = `<option value="">Operation area unavailable</option>`;
    return;
  }

  refs.operationAreaSelect.innerHTML = appState.operationAreas
    .map((area, index) => (
      `<option value="${index}">${area.name} · ${area.lat.toFixed(4)}, ${area.lon.toFixed(4)}</option>`
    ))
    .join("");
}

function projectGeoCoordinate(lon, lat, bbox) {
  const [minLon, minLat, maxLon, maxLat] = bbox;
  const mapWidth = 1000;
  const mapHeight = 600;
  const padding = 34;
  const drawableWidth = mapWidth - padding * 2;
  const drawableHeight = mapHeight - padding * 2;

  return [
    padding + ((lon - minLon) / (maxLon - minLon)) * drawableWidth,
    padding + ((maxLat - lat) / (maxLat - minLat)) * drawableHeight
  ];
}

function coordinatesToPath(coordinates, bbox) {
  return coordinates
    .map((ring) => ring
      .map(([lon, lat], index) => {
        const [x, y] = projectGeoCoordinate(lon, lat, bbox);
        return `${index === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
      })
      .join(" ") + " Z")
    .join(" ");
}

function renderGeoJson(geoJson) {
  refs.geoJsonLayer.innerHTML = "";
  const bbox = getGeoJsonBbox(geoJson);
  const features = Array.isArray(geoJson.features) ? geoJson.features : [];

  if (!bbox || !features.length) {
    refs.geoJsonStatus.textContent = "GeoJSON Layer: invalid data";
    return;
  }

  appState.mapBbox = bbox;

  features.forEach((feature) => {
    const geometry = feature.geometry || {};
    const polygons = geometry.type === "Polygon"
      ? [geometry.coordinates]
      : geometry.type === "MultiPolygon"
        ? geometry.coordinates
        : [];

    polygons.forEach((polygon) => {
      const path = document.createElementNS(SVG_NS, "path");
      path.setAttribute("class", "geo-json-boundary");
      path.setAttribute("d", coordinatesToPath(polygon, bbox));
      refs.geoJsonLayer.appendChild(path);
    });
  });

  appState.operationAreas = extractOperationAreas(geoJson);
  renderOperationAreaOptions();
  refs.geoJsonStatus.textContent = `GeoJSON Layer: ${features.length} features loaded`;
}

async function loadGeoJsonLayer() {
  refs.geoJsonStatus.textContent = "Base Map: ready · GeoJSON loading";

  for (const path of APP_CONFIG.geoJsonPaths) {
    try {
      const response = await fetch(path);
      if (!response.ok) continue;
      renderGeoJson(await response.json());
      return;
    } catch {
      // Try the next path. This supports both project-root and nested static servers.
    }
  }

  refs.geoJsonStatus.textContent = "Base Map: ready · GeoJSON load failed";
}

function renderMap() {
  refs.routeLayer.innerHTML = "";
  refs.vehicleLayer.innerHTML = "";

  appState.assets.forEach((asset) => {
    if (appState.visibleLayers.route && Array.isArray(asset.route) && asset.route.length >= 2) {
      const route = document.createElementNS(SVG_NS, "polyline");
      route.setAttribute("points", routePointsToText(asset.route));
      route.setAttribute("class", `route-path ${asset.type.toLowerCase()}`);
      route.setAttribute("opacity", asset.id === appState.selectedId ? "1" : "0.52");
      refs.routeLayer.appendChild(route);
    }

    if (!Number.isFinite(asset.x) || !Number.isFinite(asset.y)) return;

    const markerGroup = document.createElementNS(SVG_NS, "g");
    markerGroup.setAttribute("class", `vehicle-marker ${asset.id === appState.selectedId ? "selected" : ""}`);
    markerGroup.addEventListener("click", () => {
      appState.selectedId = asset.id;
      renderAll();
    });

    const halo = document.createElementNS(SVG_NS, "circle");
    halo.setAttribute("class", "marker-halo");
    halo.setAttribute("cx", asset.x);
    halo.setAttribute("cy", asset.y);
    halo.setAttribute("r", asset.id === appState.selectedId ? "15" : "10");

    const body = document.createElementNS(SVG_NS, "circle");
    body.setAttribute("class", "marker-body");
    body.setAttribute("cx", asset.x);
    body.setAttribute("cy", asset.y);
    body.setAttribute("r", "6");
    body.setAttribute("fill", typeColor[asset.type] || "#ffffff");

    const label = document.createElementNS(SVG_NS, "text");
    label.setAttribute("class", "marker-label");
    label.setAttribute("x", asset.x + 10);
    label.setAttribute("y", asset.y - 11);
    label.textContent = `${asset.type} ${asset.id.split("_")[1] || asset.id}`;

    markerGroup.append(halo, body, label);
    refs.vehicleLayer.appendChild(markerGroup);
  });

  refs.mapStage.classList.toggle("awaiting-fleet", !appState.assets.length);
}

function renderLayerVisibility() {
  const bindings = { road: "roadLayer", water: "waterLayer", route: "routeLayer" };
  Object.entries(bindings).forEach(([key, id]) => {
    const element = document.getElementById(id);
    element?.classList.toggle("hidden", !appState.visibleLayers[key]);
  });

  document.querySelectorAll(".map-layer-button").forEach((button) => {
    button.classList.toggle("active", appState.visibleLayers[button.dataset.layer]);
  });
}

function renderAlerts() {
  const visibleAlerts = appState.alerts.filter((alert) => appState.activeFilter === "ALL" || alert.severity === appState.activeFilter);
  refs.alertList.innerHTML = "";

  if (!visibleAlerts.length) {
    refs.alertList.innerHTML = `<div class="empty-state">No live alerts.<br />Waiting for <code>/c2/alerts</code>.</div>`;
  } else {
    visibleAlerts.forEach((alert) => {
      const alertCard = document.createElement("button");
      alertCard.className = `alert-card ${alert.severity}`;
      alertCard.innerHTML = `
        <div class="alert-top-row">
          <span class="alert-level">${alert.severity} · ${alert.vehicleId.replace("_", "-")}</span>
          <span class="alert-time">${alert.time}</span>
        </div>
        <p class="alert-title">${alert.title}</p>
        <p class="alert-recommendation"><strong>AI:</strong> ${alert.recommendation}</p>
      `;
      alertCard.addEventListener("click", () => {
        appState.selectedId = alert.vehicleId;
        renderAll();
      });
      refs.alertList.appendChild(alertCard);
    });
  }

  refs.alertCounter.textContent = appState.alerts.filter((alert) => alert.severity !== "GREEN").length;
}

function renderLogs(target, logs, waitTopic) {
  target.innerHTML = "";
  if (!logs.length) {
    target.innerHTML = `<div class="empty-state">No log entries.<br />Waiting for <code>${waitTopic}</code>.</div>`;
    return;
  }
  logs.slice(0, 8).forEach((log) => {
    const entry = document.createElement("div");
    entry.className = `log-entry ${log.type || ""}`;
    entry.innerHTML = `<span class="log-time">[${log.time}]</span>${log.text}`;
    target.appendChild(entry);
  });
}

function publishRos(topic, data) {
  if (!rosSocket || rosSocket.readyState !== WebSocket.OPEN) {
    addAutopilotLog("warning", "LOCAL", `ROS command not sent: ${topic} (ROSBridge disconnected).`);
    return false;
  }
  rosSocket.send(JSON.stringify({
    op: "publish",
    topic,
    msg: { data: JSON.stringify(data) }
  }));
  return true;
}

function sendCommand(command) {
  const asset = getSelectedAsset();
  if (!asset) {
    addAutopilotLog("warning", getKstTime(), `Operator command ${command} ignored: no live asset selected.`);
    renderAll();
    return;
  }

  const now = getKstTime();
  const selectedAreaIndex = refs.operationAreaSelect ? Number(refs.operationAreaSelect.value) : -1;
  const selectedArea = command === "MOVE_TO"
    ? appState.operationAreas[selectedAreaIndex]
    : null;

  if (command === "MOVE_TO" && !selectedArea) {
    addAutopilotLog("warning", now, "MOVE_TO ignored: no operation area selected.");
    renderAll();
    return;
  }

  const payload = {
    event_type: "OPERATOR_COMMAND",
    command_id: `CMD_${Date.now()}`,
    vehicle_id: asset.id,
    command,
    source: "WEB_C2",
    requested_at: new Date().toISOString()
  };
  if (selectedArea) {
    payload.target_area = selectedArea.name;
    payload.target_lat = selectedArea.lat;
    payload.target_lon = selectedArea.lon;
    payload.target_alt_m = asset.alt || 50;
  }

  appState.operatorActionCount += 1;
  appState.missionLogs.unshift({
    type: "manual",
    time: now,
    text: `${asset.id.replace("_", "-")} ${command}${selectedArea ? ` ${selectedArea.name}` : ""} command requested by operator. Waiting for PX4 ACK.`
  });
  appState.autopilotLogs.unshift({
    type: "manual",
    time: now,
    text: `WEB_C2 published ${command}${selectedArea ? ` target ${selectedArea.lat.toFixed(5)}, ${selectedArea.lon.toFixed(5)}` : ""} to ${APP_CONFIG.topics.operatorCommand}.`
  });

  publishRos(APP_CONFIG.topics.operatorCommand, payload);
  renderAll();
}

function addAutopilotLog(type, time, text) {
  appState.autopilotLogs.unshift({ type, time, text });
}

function normalizeAsset(raw) {
  const type = raw.vehicle_type || raw.type || "UAV";
  const position = raw.position || {};
  const linkRaw = raw.link_quality ?? raw.comm_quality ?? raw.link ?? 0;
  const link = linkRaw <= 1 ? linkRaw * 100 : linkRaw;
  const lat = Number(raw.lat ?? raw.latitude ?? position.lat ?? 0);
  const lon = Number(raw.lon ?? raw.longitude ?? position.lon ?? 0);
  const projected = Number.isFinite(lat) && Number.isFinite(lon)
    ? projectGeoCoordinate(lon, lat, appState.mapBbox)
    : [undefined, undefined];
  const mapX = Number(raw.map_x ?? raw.x);
  const mapY = Number(raw.map_y ?? raw.y);
  const navRaw = raw.nav_confidence ?? raw.gps_confidence ?? raw.comm_quality ?? 0;

  return {
    id: raw.vehicle_id || raw.id,
    type,
    subtype: raw.subtype || type,
    icon: raw.icon || iconForType(type),
    role: raw.role || "No assigned role",
    battery: Number(raw.battery_pct ?? raw.battery ?? 0),
    link: Number(link),
    speed: Number(raw.speed_mps ?? raw.speed ?? 0),
    navConfidence: Math.round(navRaw <= 1 ? navRaw * 100 : navRaw),
    assignable: Boolean(raw.assignable ?? raw.assignment_possible),
    alert: raw.alert_level || raw.alert || ({ good: "GREEN", caution: "AMBER", critical: "RED", disabled: "RED" }[raw.device_state] || "GREEN"),
    missionState: raw.mission_state || raw.status || raw.mission_status || "UNKNOWN",
    mission: raw.current_mission || raw.mission || "No mission assigned",
    cameraMode: raw.camera_mode || "CAMERA / NO FEED",
    cameraStatus: raw.camera_status || "Telemetry synchronized",
    lat,
    lon,
    alt: Number(raw.alt_m ?? raw.alt ?? 0),
    x: Number.isFinite(mapX) ? mapX : projected[0],
    y: Number.isFinite(mapY) ? mapY : projected[1],
    route: Array.isArray(raw.route) ? raw.route : []
  };
}

function handleFleetPayload(data) {
  const incomingAssets = Array.isArray(data) ? data : (data.assets || []);
  appState.assets = incomingAssets
    .map(normalizeAsset)
    .filter(asset => asset.id);

  ensureSelectedAsset();
  renderAll();
}

function handleAlertPayload(data) {
  const raw = Array.isArray(data) ? data[0] : data;
  if (!raw) return;
  appState.alerts.unshift({
    id: raw.alert_id || `ALERT_${Date.now()}`,
    vehicleId: raw.vehicle_id || raw.vehicleId || "UNKNOWN",
    severity: raw.severity || raw.alert_level || "AMBER",
    title: raw.reason || raw.title || "Live alert received",
    recommendation: raw.recommended_action || raw.recommendation || "Review required.",
    time: raw.time || getKstTime()
  });
  renderAll();
}

function handleLogPayload(data, kind) {
  const raw = typeof data === "string" ? { text: data } : data;
  const target = kind === "mission" ? appState.missionLogs : appState.autopilotLogs;
  target.unshift({
    type: raw.type || (kind === "mission" ? "manual" : "auto"),
    time: raw.time || getKstTime(),
    text: raw.text || raw.message || JSON.stringify(raw)
  });
  renderAll();
}

function decodeRosData(msg) {
  if (msg && typeof msg.data === "string") {
    try { return JSON.parse(msg.data); } catch { return msg.data; }
  }
  return msg;
}

function subscribeRos(topic) {
  rosSocket.send(JSON.stringify({
    op: "subscribe",
    topic,
    type: "std_msgs/msg/String"
  }));
}

function connectRos() {
  if (rosSocket && rosSocket.readyState === WebSocket.OPEN) {
    rosSocket.close();
    return;
  }

  setConnectionState(false, "ROS CONNECTING · WAITING FOR ROSBRIDGE");

  try {
    rosSocket = new WebSocket(APP_CONFIG.rosBridgeUrl);
  } catch {
    setConnectionState(false);
    return;
  }

  rosSocket.onopen = () => {
    setConnectionState(true);
    Object.values(APP_CONFIG.topics)
      .filter(topic => topic !== APP_CONFIG.topics.operatorCommand)
      .forEach(subscribeRos);
  };

  rosSocket.onclose = () => setConnectionState(false);
  rosSocket.onerror = () => setConnectionState(false, "ROS ERROR · ROSBRIDGE NOT AVAILABLE");

  rosSocket.onmessage = (event) => {
    let message;
    try { message = JSON.parse(event.data); } catch { return; }
    if (message.op !== "publish") return;

    const data = decodeRosData(message.msg);
    switch (message.topic) {
      case APP_CONFIG.topics.fleetState:
        handleFleetPayload(data);
        break;
      case APP_CONFIG.topics.alerts:
        handleAlertPayload(data);
        break;
      case APP_CONFIG.topics.autopilotLog:
        handleLogPayload(data, "autopilot");
        break;
      case APP_CONFIG.topics.missionLog:
        handleLogPayload(data, "mission");
        break;
      default:
        break;
    }
  };
}

function enableDemoData() {
  appState.assets = [
    {
      id: "UAV_01", type: "UAV", subtype: "Fixed-wing", icon: "✈", role: "Wide-area ISR",
      battery: 82, link: 93, speed: 23.4, navConfidence: 95, assignable: true,
      alert: "GREEN", missionState: "EXECUTING", mission: "Recon · Mountain Sector A",
      cameraMode: "EO / LIVE", cameraStatus: "Demo telemetry", lat: 37.8112, lon: 128.0405,
      alt: 420, x: 548, y: 171, route: []
    },
    {
      id: "UAV_02", type: "UAV", subtype: "Multicopter", icon: "◈", role: "Target confirmation",
      battery: 44, link: 78, speed: 14.2, navConfidence: 81, assignable: true,
      alert: "AMBER", missionState: "STANDBY", mission: "Standby · Target reacquisition",
      cameraMode: "EO / IR LIVE", cameraStatus: "Demo telemetry", lat: 37.5625, lon: 127.0039,
      alt: 120, x: 574, y: 333, route: []
    },
    {
      id: "UGV_01", type: "UGV", subtype: "Rover", icon: "▣", role: "Ground investigation",
      battery: 67, link: 72, speed: 5.8, navConfidence: 98, assignable: true,
      alert: "AMBER", missionState: "EXECUTING", mission: "Investigate · Urban Access Route",
      cameraMode: "THERMAL / LIVE", cameraStatus: "Demo telemetry", lat: 37.5317, lon: 126.9879,
      alt: 0, x: 470, y: 355, route: []
    },
    {
      id: "USV_01", type: "USV", subtype: "Surface vessel", icon: "⛵", role: "Coastal surveillance",
      battery: 91, link: 88, speed: 9.3, navConfidence: 92, assignable: false,
      alert: "RED", missionState: "TRACKING", mission: "Track · Maritime intrusion indicator",
      cameraMode: "EO / TARGET LOCK", cameraStatus: "Demo telemetry", lat: 37.4488, lon: 126.3610,
      alt: 0, x: 219, y: 405, route: []
    }
  ];
  appState.alerts = [
    { id:"A-401", vehicleId:"USV_01", severity:"RED", title:"Potential intrusion vector detected in Water Corridor W3", recommendation:"Maintain track and request operator review.", time:"10:24:18" },
    { id:"A-402", vehicleId:"UAV_02", severity:"AMBER", title:"Battery reserve will cross return threshold in 6 min", recommendation:"Reassign confirmation task to UAV-01 or UGV-01.", time:"10:23:41" },
    { id:"A-403", vehicleId:"UGV_01", severity:"AMBER", title:"Road edge R4-R6 has been blocked", recommendation:"Auto-reroute through R2-R5-R8.", time:"10:22:52" }
  ];
  appState.autopilotLogs = [
    { type:"auto", time:"10:21:05", text:"[DEMO] UAV-01 navigation confidence recovered. Low-risk event auto-resolved." },
    { type:"warning", time:"10:22:53", text:"[DEMO] UGV-01 road closure detected. Reroute candidate generated." }
  ];
  appState.missionLogs = [
    { type:"manual", time:"10:18:02", text:"[DEMO] Operator assigned UGV-01 to investigate Urban Access Route." }
  ];
  ensureSelectedAsset();
  refs.demoModeBadge.classList.remove("hidden");
  refs.systemStatus.textContent = "DEMO MODE · MOCK TELEMETRY ONLY";
  refs.geoJsonStatus.textContent = "GeoJSON Layer: demonstration mock";
}

function bindEvents() {
  document.querySelectorAll(".map-layer-button").forEach((button) => {
    button.addEventListener("click", () => {
      const key = button.dataset.layer;
      appState.visibleLayers[key] = !appState.visibleLayers[key];
      renderLayerVisibility();
      renderMap();
    });
  });

  document.querySelectorAll(".alert-filter").forEach((button) => {
    button.addEventListener("click", () => {
      appState.activeFilter = button.dataset.filter;
      document.querySelectorAll(".alert-filter").forEach((filterButton) => {
        filterButton.classList.toggle("active", filterButton === button);
      });
      renderAlerts();
    });
  });

  document.querySelectorAll(".mission-btn").forEach((button) => {
    button.addEventListener("click", () => sendCommand(button.dataset.command));
  });

  refs.connectRosButton.addEventListener("click", connectRos);

  refs.clearAutoLogButton.addEventListener("click", () => {
    appState.autopilotLogs = [];
    renderAll();
  });
}

function renderAll() {
  ensureSelectedAsset();
  renderEquipmentList();
  renderDetailPanel();
  renderMap();
  renderLayerVisibility();
  renderAlerts();
  renderLogs(refs.autopilotLog, appState.autopilotLogs, APP_CONFIG.topics.autopilotLog);
  renderLogs(refs.missionLog, appState.missionLogs, APP_CONFIG.topics.missionLog);
}

bindEvents();
removeLegacyMapOverlay();
updateClock();
setConnectionState(false);
loadGeoJsonLayer();

if (APP_CONFIG.demoMode) {
  enableDemoData();
}

renderAll();
setInterval(updateClock, 1000);
