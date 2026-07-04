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
    "./res/TL_SCCO_CTPRVN.json?v=20260704-mapfit2",
    "../res/TL_SCCO_CTPRVN.json?v=20260704-mapfit2",
    "../../res/TL_SCCO_CTPRVN.json?v=20260704-mapfit2",
    "/res/TL_SCCO_CTPRVN.json?v=20260704-mapfit2"
  ],
  visionVideoPaths: [
    "./res/uav1.webm",
    "../res/uav1.webm",
    "../../res/uav1.webm",
    "/res/uav1.webm"
  ],
  yoloModelPaths: [
    "./res/best.pt",
    "../res/best.pt",
    "../../res/best.pt",
    "/res/best.pt"
  ],
  topics: {
    fleetState: "/c2/fleet/state",
    waypointNodes: "/missiondeck/map/waypoint_nodes",
    riskZones: "/missiondeck/map/risk_zones",
    plannerRequest: "/missiondeck/planner/request",
    routeCandidates: "/missiondeck/planner/route_candidates",
    selectedRoute: "/missiondeck/planner/selected_route",
    alerts: "/c2/alerts",
    visionDetections: "/c2/vision/uav1/detections",
    autopilotLog: "/c2/autopilot_log",
    missionLog: "/c2/mission_log",
    operatorCommand: "/c2/operator_command"
  }
};

const appState = {
  selectedId: null,
  activeFilter: "ALL",
  assetTypeFilters: {
    UAV: true,
    UGV: true,
    USV: true
  },
  visibleLayers: {
    road: true,
    water: true,
    route: true
  },/*  */
  operationAreas: [],
  mapNodes: [],
  riskZones: [],
  routeCandidates: [],
  selectedRoute: null,
  geoJsonData: null,
  baseMapBbox: [124.7893155286271, 33.172610584346295, 130.96524575425667, 38.54255349620522],
  mapBbox: [124.7893155286271, 33.172610584346295, 130.96524575425667, 38.54255349620522],
  operatorActionCount: 0,
  rosConnected: false,
  assets: [],
  alerts: [],
  autopilotLogs: [],
  missionLogs: [],
  alertOverrides: {},
  vision: {
    videoPath: null,
    modelPath: null,
    modelLoaded: false,
    backendOnline: null,
    active: false,
    activeAssetId: null,
    detections: [],
    renderFrameId: null,
    lastDetectionAt: 0
  }
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
  enemySpotStatus: document.getElementById("enemySpotStatus"),
  stateData: document.getElementById("stateData"),
  missionDescription: document.getElementById("missionDescription"),
  cameraMode: document.getElementById("cameraMode"),
  cameraClock: document.getElementById("cameraClock"),
  cameraText: document.getElementById("cameraText"),
  cameraStatus: document.getElementById("cameraStatus"),
  cameraSignalBars: document.getElementById("cameraSignalBars"),
  cameraBox: document.querySelector(".camera-box"),
  uavVisionVideo: document.getElementById("uavVisionVideo"),
  visionOverlayCanvas: document.getElementById("visionOverlayCanvas"),
  autopilotLog: document.getElementById("autopilotLog"),
  missionLog: document.getElementById("missionLog"),
  clearAutoLogButton: document.getElementById("clearAutoLogButton"),
  operationAreaSelect: document.getElementById("operationAreaSelect"),
  geoJsonLayer: document.getElementById("geoJsonLayer"),
  riskZoneLayer: document.getElementById("riskZoneLayer"),
  roadLayer: document.getElementById("roadLayer"),
  waterLayer: document.getElementById("waterLayer"),
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

const HEADQUARTERS = {
  name: "Headquarters",
  address: "부산 남구 우암로 263",
  lat: 35.124333,
  lon: 129.064000
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
  return { UAV: "✈", UGV: "🚗", USV: "⛵" }[type] || "●";
}

function alertLabel(level) {
  return { GREEN: "Normal", AMBER: "Caution", RED: "Critical" }[level] || level || "Unknown";
}

function getSelectedAsset() {
  return appState.assets.find((asset) => asset.id === appState.selectedId) || null;
}

function visibleAssets() {
  return appState.assets.filter((asset) => appState.assetTypeFilters[asset.type] !== false);
}

function ensureSelectedAsset() {
  const filteredAssets = visibleAssets();
  if (!appState.selectedId && filteredAssets.length) {
    appState.selectedId = filteredAssets[0].id;
  }
  if (appState.selectedId && !filteredAssets.some(a => a.id === appState.selectedId)) {
    appState.selectedId = filteredAssets.length ? filteredAssets[0].id : null;
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

function resetLiveData(detail = "ROS OFFLINE · WAITING FOR FLEET STATE") {
  appState.selectedId = null;
  appState.operatorActionCount = 0;
  appState.assets = [];
  appState.alerts = [];
  appState.autopilotLogs = [];
  appState.missionLogs = [];
  appState.alertOverrides = {};
  appState.routeCandidates = [];
  appState.selectedRoute = null;
  appState.mapBbox = Array.isArray(appState.baseMapBbox)
    ? appState.baseMapBbox.slice()
    : appState.mapBbox;
  stopUav1Vision();
  appState.vision.active = false;
  appState.vision.activeAssetId = null;
  appState.vision.detections = [];
  appState.vision.backendOnline = null;
  appState.vision.lastDetectionAt = 0;
  if (appState.geoJsonData) {
    renderGeoJson(appState.geoJsonData, appState.mapBbox);
  }
  setConnectionState(false, detail);
  renderAll();
}

async function resolveReachablePath(paths, options = {}) {
  const method = options.method || "HEAD";
  for (const path of paths) {
    try {
      const response = await fetch(path, { method, cache: "no-store" });
      if (response.ok) return path;
    } catch {
      // Try the next path. Resource paths differ depending on static-server root.
    }
  }
  return null;
}

async function initializeVisionAssets() {
  const [videoPath, modelPath] = await Promise.all([
    resolveReachablePath(APP_CONFIG.visionVideoPaths),
    resolveReachablePath(APP_CONFIG.yoloModelPaths, { method: "GET" })
  ]);

  appState.vision.videoPath = videoPath;
  appState.vision.modelPath = modelPath;
  appState.vision.modelLoaded = Boolean(modelPath);

  if (videoPath && refs.uavVisionVideo) {
    refs.uavVisionVideo.src = videoPath;
    refs.uavVisionVideo.load();
  }

  syncVisionForSelectedAsset(getSelectedAsset());
}

function normalizeVehicleId(id) {
  const compact = String(id || "").replace(/[^a-zA-Z0-9]/g, "").toUpperCase();
  return compact.replace(/^([A-Z]+)0+(\d+)$/, "$1$2");
}

function isUav1Asset(asset) {
  if (!asset) return false;
  return normalizeVehicleId(asset.id) === "UAV1";
}

function clearVisionOverlay() {
  const canvas = refs.visionOverlayCanvas;
  if (!canvas) return;
  const context = canvas.getContext("2d");
  context.clearRect(0, 0, canvas.width, canvas.height);
}

function startVisionRenderLoop() {
  if (appState.vision.renderFrameId) return;

  const draw = () => {
    if (!appState.vision.active) {
      appState.vision.renderFrameId = null;
      return;
    }

    drawVisionDetections();
    appState.vision.renderFrameId = requestAnimationFrame(draw);
  };

  appState.vision.renderFrameId = requestAnimationFrame(draw);
}

function stopVisionRenderLoop() {
  if (appState.vision.renderFrameId) {
    cancelAnimationFrame(appState.vision.renderFrameId);
    appState.vision.renderFrameId = null;
  }
}

function drawVisionDetections() {
  const video = refs.uavVisionVideo;
  const canvas = refs.visionOverlayCanvas;
  if (!video || !canvas) return;

  const width = video.videoWidth || canvas.clientWidth || 640;
  const height = video.videoHeight || canvas.clientHeight || 360;
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }

  const context = canvas.getContext("2d");
  context.clearRect(0, 0, width, height);

  appState.vision.detections.forEach((detection) => {
    const [x1, y1, x2, y2] = detection.bbox || [];
    if (![x1, y1, x2, y2].every(Number.isFinite)) return;

    const label = detection.label || detection.class_name || "object";
    const confidence = Number(detection.confidence ?? detection.conf ?? 0);
    const caption = `${label} ${(confidence * 100).toFixed(0)}%`;
    const boxWidth = Math.max(1, x2 - x1);
    const boxHeight = Math.max(1, y2 - y1);

    context.strokeStyle = "#ff3f49";
    context.lineWidth = Math.max(2, width * 0.003);
    context.strokeRect(x1, y1, boxWidth, boxHeight);

    context.font = `${Math.max(12, Math.round(width * 0.022))}px monospace`;
    const textWidth = context.measureText(caption).width;
    const labelHeight = Math.max(18, Math.round(width * 0.035));
    const labelY = Math.max(0, y1 - labelHeight);

    context.fillStyle = "rgba(255, 63, 73, 0.92)";
    context.fillRect(x1, labelY, textWidth + 10, labelHeight);
    context.fillStyle = "#fff7f7";
    context.fillText(caption, x1 + 5, labelY + labelHeight - 5);
  });
}

function startUav1Vision(asset) {
  if (!refs.uavVisionVideo || !refs.visionOverlayCanvas || !refs.cameraBox) return;

  const alreadyActive = appState.vision.active && appState.vision.activeAssetId === asset.id;
  appState.vision.active = true;
  appState.vision.activeAssetId = asset.id;

  refs.cameraBox.classList.add("vision-live");
  refs.uavVisionVideo.classList.remove("hidden");
  refs.visionOverlayCanvas.classList.remove("hidden");
  startVisionRenderLoop();

  if (alreadyActive) {
    return;
  }

  if (appState.vision.videoPath && refs.uavVisionVideo.src !== new URL(appState.vision.videoPath, window.location.href).href) {
    refs.uavVisionVideo.src = appState.vision.videoPath;
    refs.uavVisionVideo.load();
  }

  refs.cameraMode.textContent = "EO / YOLO DETECT";
  refs.cameraText.textContent = `${asset.id.replace("_", "-")} · ${appState.vision.modelLoaded ? "best.pt loaded" : "model pending"}`;
  refs.cameraStatus.textContent = asset.cameraStatus?.startsWith("YOLO")
    ? asset.cameraStatus
    : appState.rosConnected
      ? `Waiting for ${APP_CONFIG.topics.visionDetections}`
      : "Connect ROS to receive YOLO detections";

  refs.uavVisionVideo.currentTime = 0;
  refs.uavVisionVideo.play().catch(() => {
    refs.cameraStatus.textContent = "UAV1 video ready · playback blocked by browser";
  });
}

function stopUav1Vision() {
  if (!appState.vision.active) return;

  appState.vision.active = false;
  appState.vision.activeAssetId = null;
  appState.vision.detections = [];
  stopVisionRenderLoop();
  clearVisionOverlay();

  refs.cameraBox?.classList.remove("vision-live");
  refs.uavVisionVideo?.classList.add("hidden");
  refs.visionOverlayCanvas?.classList.add("hidden");
  refs.uavVisionVideo?.pause();
}

function syncVisionForSelectedAsset(asset) {
  if (isUav1Asset(asset)) {
    startUav1Vision(asset);
  } else {
    stopUav1Vision();
  }
}

function valueClass(value, warningThreshold, dangerThreshold) {
  if (value <= dangerThreshold) return "value-red";
  if (value <= warningThreshold) return "value-amber";
  return "value-green";
}

function isEnemySpottedForAsset(asset) {
  if (!asset) return false;
  const override = overrideForVehicle(asset.id);
  return Boolean(
    override?.enemySpotted ||
    (isUav1Asset(asset) && appState.vision.detections.length > 0)
  );
function signalClassForQuality(commQuality) {
  const raw = Number(commQuality);
  const pct = Math.max(0, Math.min(100, raw <= 1 ? raw * 100 : raw));
  const bars = pct <= 0 ? 0 : Math.max(1, Math.ceil(pct / 25));
  const level = bars === 0 ? "offline" : pct <= 35 ? "critical" : pct <= 65 ? "caution" : "good";
  return `signal-bars signal-${bars} ${level}`;
}

function renderCameraSignal(commQuality = 0) {
  if (!refs.cameraSignalBars) return;
  const raw = Number(commQuality);
  const pct = Math.max(0, Math.min(100, raw <= 1 ? raw * 100 : raw));
  refs.cameraSignalBars.className = signalClassForQuality(commQuality);
  refs.cameraSignalBars.setAttribute("aria-label", `Signal quality ${Math.round(pct)} percent`);
}

function renderEquipmentList() {
  refs.equipmentList.innerHTML = "";
  const filteredAssets = visibleAssets();

  if (!appState.assets.length) {
    refs.equipmentList.innerHTML = `<div class="empty-state">No connected UxV assets.<br />Waiting for <code>/c2/fleet/state</code>.</div>`;
  } else if (!filteredAssets.length) {
    refs.equipmentList.innerHTML = `<div class="empty-state">No assets match the selected filters.</div>`;
  } else {
    filteredAssets.forEach((asset) => {
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

  refs.assetTotal.textContent = filteredAssets.length === appState.assets.length
    ? appState.assets.length
    : `${filteredAssets.length}/${appState.assets.length}`;
  refs.assignableCount.textContent = `${filteredAssets.filter((asset) => asset.assignable).length} / ${filteredAssets.length}`;
  refs.operatorActionCount.textContent = appState.operatorActionCount;
}

function renderDetailPanel() {
  const asset = getSelectedAsset();

  if (!asset) {
    refs.selectedAssetTitle.textContent = "No asset selected";
    refs.enemySpotStatus?.classList.add("hidden");
    refs.stateData.innerHTML = `
      <dt>id</dt><dd class="waiting-state">—</dd>
      <dt>type</dt><dd class="waiting-state">—</dd>
      <dt>battery</dt><dd class="waiting-state">—</dd>
      <dt>comm_quality</dt><dd class="waiting-state">—</dd>
      <dt>device_state</dt><dd class="waiting-state">—</dd>
      <dt>mission_status</dt><dd class="waiting-state">—</dd>
      <dt>speed</dt><dd class="waiting-state">—</dd>
      <dt>assignment_possible</dt><dd class="waiting-state">—</dd>
      <dt>latitude</dt><dd class="waiting-state">—</dd>
      <dt>longitude</dt><dd class="waiting-state">—</dd>
    `;
    refs.missionDescription.textContent = "Waiting for an asset selection from live fleet telemetry.";
    refs.cameraMode.textContent = "CAMERA / OFFLINE";
    refs.cameraText.textContent = "No live asset selected";
    refs.cameraStatus.textContent = "No video or telemetry source";
    renderCameraSignal(0);
    syncVisionForSelectedAsset(null);
    return;
  }

  refs.selectedAssetTitle.textContent = `${asset.id.replace("_", "-")} · ${asset.type}`;
  const enemySpotted = isEnemySpottedForAsset(asset);
  refs.enemySpotStatus?.classList.toggle("hidden", !enemySpotted);

  const uxvState = asset.uxvState;
  const commQualityPct = uxvState.comm_quality * 100;
  const speedKmh = uxvState.speed_mps * 3.6;
  refs.stateData.innerHTML = `
    <dt>id</dt><dd>${uxvState.id}</dd>
    <dt>type</dt><dd>${uxvState.type}</dd>
    <dt>battery</dt><dd class="${valueClass(uxvState.battery, 55, 35)}">${uxvState.battery.toFixed(1)}%</dd>
    <dt>comm_quality</dt><dd class="${valueClass(commQualityPct, 80, 65)}">${commQualityPct.toFixed(0)}%</dd>
    <dt>device_state</dt><dd>${uxvState.device_state}</dd>
    <dt>mission_status</dt><dd>${uxvState.mission_status}</dd>
    <dt>speed</dt><dd>${speedKmh.toFixed(1)} km/h</dd>
    <dt>assignment_possible</dt><dd class="${uxvState.assignment_possible ? "value-green" : "value-red"}">${uxvState.assignment_possible}</dd>
    <dt>latitude</dt><dd>${uxvState.position.lat.toFixed(4)}</dd>
    <dt>longitude</dt><dd>${uxvState.position.lon.toFixed(4)}</dd>
  `;

  refs.missionDescription.textContent = asset.mission || "No mission assigned";
  refs.cameraMode.textContent = asset.cameraMode || "CAMERA / NO FEED";
  refs.cameraText.textContent = `${asset.id.replace("_", "-")} · ${asset.role || asset.type}`;
  refs.cameraStatus.textContent = asset.cameraStatus || "Telemetry synchronized";
  renderCameraSignal(uxvState.comm_quality);
  syncVisionForSelectedAsset(asset);
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

  const previousValue = refs.operationAreaSelect.value;
  const asset = getSelectedAsset();
  const assetType = asset?.type || "";
  const destinationNodes = appState.mapNodes
    .filter((node) => !assetType || node.allowedTypes.includes(assetType) || assetType === "UAV")
    .sort((a, b) => {
      if (a.domain !== b.domain) return a.domain.localeCompare(b.domain);
      return a.name.localeCompare(b.name, "ko");
    });

  if (destinationNodes.length) {
    refs.operationAreaSelect.innerHTML = destinationNodes
      .map((node) => (
        `<option value="node:${node.id}">${node.name} · ${node.domain.toUpperCase()} · ${node.lat.toFixed(4)}, ${node.lon.toFixed(4)}</option>`
      ))
      .join("");
    if ([...refs.operationAreaSelect.options].some((option) => option.value === previousValue)) {
      refs.operationAreaSelect.value = previousValue;
    }
    return;
  }

  if (appState.operationAreas.length) {
    refs.operationAreaSelect.innerHTML = appState.operationAreas
      .map((area, index) => (
        `<option value="area:${index}">${area.name} · ${area.lat.toFixed(4)}, ${area.lon.toFixed(4)}</option>`
      ))
      .join("");
    if ([...refs.operationAreaSelect.options].some((option) => option.value === previousValue)) {
      refs.operationAreaSelect.value = previousValue;
    }
    return;
  }

  refs.operationAreaSelect.innerHTML = `<option value="">Destination node unavailable</option>`;
}

function projectGeoCoordinate(lon, lat, bbox) {
  const [minLon, minLat, maxLon, maxLat] = bbox;
  const mapWidth = 1000;
  const mapHeight = 600;
  const padding = 34;
  const drawableWidth = mapWidth - padding * 2;
  const drawableHeight = mapHeight - padding * 2;
  const lonRange = maxLon - minLon;
  const latRange = maxLat - minLat;

  if (!Number.isFinite(lonRange) || !Number.isFinite(latRange) || lonRange <= 0 || latRange <= 0) {
    return [mapWidth / 2, mapHeight / 2];
  }

  const x = padding + ((lon - minLon) / lonRange) * drawableWidth;
  const y = padding + ((maxLat - lat) / latRange) * drawableHeight;

  return [
    Math.max(0, Math.min(mapWidth, x)),
    Math.max(0, Math.min(mapHeight, y))
  ];
}

function getRawAssetCoordinate(raw) {
  const position = raw?.position || {};
  const lat = Number(raw?.lat ?? raw?.latitude ?? position.lat);
  const lon = Number(raw?.lon ?? raw?.longitude ?? position.lon);
  return Number.isFinite(lat) && Number.isFinite(lon) ? { lat, lon } : null;
}

function padBbox(bbox) {
  const lonRange = Math.max(bbox[2] - bbox[0], 0.02);
  const latRange = Math.max(bbox[3] - bbox[1], 0.02);
  const lonPad = Math.max(lonRange * 0.08, 0.02);
  const latPad = Math.max(latRange * 0.08, 0.02);
  return [bbox[0] - lonPad, bbox[1] - latPad, bbox[2] + lonPad, bbox[3] + latPad];
}

function getFleetFitBbox(rawAssets) {
  const baseBbox = Array.isArray(appState.baseMapBbox)
    ? appState.baseMapBbox.slice()
    : appState.mapBbox.slice();

  const bbox = baseBbox.slice();
  (rawAssets || []).forEach((raw) => {
    const coordinate = getRawAssetCoordinate(raw);
    if (!coordinate) return;
    bbox[0] = Math.min(bbox[0], coordinate.lon);
    bbox[1] = Math.min(bbox[1], coordinate.lat);
    bbox[2] = Math.max(bbox[2], coordinate.lon);
    bbox[3] = Math.max(bbox[3], coordinate.lat);
  });

  return padBbox(bbox);
}

function bboxChanged(a, b) {
  if (!Array.isArray(a) || !Array.isArray(b)) return true;
  return a.some((value, index) => Math.abs(value - b[index]) > 0.000001);
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

function renderGeoJson(geoJson, displayBbox = null) {
  refs.geoJsonLayer.innerHTML = "";
  const sourceBbox = getGeoJsonBbox(geoJson);
  const bbox = displayBbox || sourceBbox;
  const features = Array.isArray(geoJson.features) ? geoJson.features : [];

  if (!sourceBbox || !bbox || !features.length) {
    refs.geoJsonStatus.textContent = "GeoJSON Layer: invalid data";
    return;
  }

  appState.geoJsonData = geoJson;
  appState.baseMapBbox = sourceBbox;
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
      renderMap();
      return;
    } catch {
      // Try the next path. This supports both project-root and nested static servers.
    }
  }

  refs.geoJsonStatus.textContent = "Base Map: ready · GeoJSON load failed";
}

function normalizeMapNode(raw) {
  const position = raw?.position || {};
  const lat = Number(raw?.lat ?? raw?.latitude ?? position.lat);
  const lon = Number(raw?.lon ?? raw?.longitude ?? position.lon);
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;

  const domain = String(raw.domain || raw.node_domain || "").toLowerCase();
  return {
    id: raw.id || raw.node_id || `${domain || "node"}-${lat.toFixed(4)}-${lon.toFixed(4)}`,
    name: raw.name || raw.label || raw.id || "Waypoint node",
    domain,
    nodeKind: raw.node_kind || raw.kind || "waypoint",
    allowedTypes: Array.isArray(raw.allowed_types) ? raw.allowed_types : [],
    lat,
    lon
  };
}

function handleWaypointNodesPayload(data) {
  const incomingNodes = Array.isArray(data) ? data : (data.nodes || []);
  appState.mapNodes = incomingNodes
    .map(normalizeMapNode)
    .filter((node) => node && (node.domain === "land" || node.domain === "water"));

  renderAll();
}

function normalizeRiskZone(raw) {
  const center = raw?.center || {};
  const lat = Number(raw?.lat ?? raw?.latitude ?? center.lat);
  const lon = Number(raw?.lon ?? raw?.longitude ?? center.lon);
  const radiusKm = Number(raw?.radius_km ?? raw?.radiusKm ?? raw?.radius ?? 0);
  if (!Number.isFinite(lat) || !Number.isFinite(lon) || !Number.isFinite(radiusKm) || radiusKm <= 0) {
    return null;
  }
  return {
    id: raw.id || raw.zone_id || `RISK-${lat.toFixed(4)}-${lon.toFixed(4)}`,
    name: raw.name || raw.id || "Risk zone",
    lat,
    lon,
    radiusKm,
    severity: raw.severity || "RED",
    sourceNodeId: raw.source_node_id || raw.sourceNodeId || null
  };
}

function handleRiskZonesPayload(data) {
  const incomingZones = Array.isArray(data) ? data : (data.zones || []);
  appState.riskZones = incomingZones
    .map(normalizeRiskZone)
    .filter(Boolean);

  renderAll();
}

function renderWaypointNodes() {
  refs.roadLayer.innerHTML = "";
  refs.waterLayer.innerHTML = "";

  appState.mapNodes.forEach((node) => {
    const layer = node.domain === "water" ? refs.waterLayer : refs.roadLayer;
    layer.appendChild(createWaypointNode(node));
  });
}

function createWaypointNode(node) {
  const [x, y] = projectGeoCoordinate(node.lon, node.lat, appState.mapBbox);
  const marker = document.createElementNS(SVG_NS, "circle");
  marker.setAttribute("class", `waypoint-node ${node.domain}`);
  marker.setAttribute("cx", x.toFixed(2));
  marker.setAttribute("cy", y.toFixed(2));
  marker.setAttribute("r", node.domain === "land" ? "3.2" : "2.2");

  const title = document.createElementNS(SVG_NS, "title");
  const allowedTypes = node.allowedTypes.length ? ` · ${node.allowedTypes.join("/")}` : "";
  title.textContent = `${node.id} · ${node.name}${allowedTypes} · ${node.lat.toFixed(4)}, ${node.lon.toFixed(4)}`;
  marker.appendChild(title);
  return marker;
}

function renderRiskZones() {
  refs.riskZoneLayer.innerHTML = "";
  appState.riskZones.forEach((zone) => {
    const [x, y] = projectGeoCoordinate(zone.lon, zone.lat, appState.mapBbox);
    const lonRadiusDeg = zone.radiusKm / (111.32 * Math.max(Math.cos(zone.lat * Math.PI / 180), 0.01));
    const [edgeX] = projectGeoCoordinate(zone.lon + lonRadiusDeg, zone.lat, appState.mapBbox);
    const radiusPx = Math.max(5, Math.abs(edgeX - x));

    const marker = document.createElementNS(SVG_NS, "circle");
    marker.setAttribute("class", "risk-zone");
    marker.setAttribute("cx", x.toFixed(2));
    marker.setAttribute("cy", y.toFixed(2));
    marker.setAttribute("r", radiusPx.toFixed(2));

    const title = document.createElementNS(SVG_NS, "title");
    title.textContent = `${zone.id} · ${zone.name} · radius ${zone.radiusKm.toFixed(1)} km`;
    marker.appendChild(title);
    refs.riskZoneLayer.appendChild(marker);
  });
}

function routeCoordinatePoints(points) {
  return (points || [])
    .map((point) => {
      if (Array.isArray(point) && point.length >= 2) {
        return projectGeoCoordinate(Number(point[1]), Number(point[0]), appState.mapBbox);
      }
      return projectGeoCoordinate(Number(point.lon), Number(point.lat), appState.mapBbox);
    })
    .filter(([x, y]) => Number.isFinite(x) && Number.isFinite(y))
    .map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`)
    .join(" ");
}

function renderSelectedPlannerRoute() {
  const selected = appState.selectedRoute?.selected;
  const routePoints = selected?.route_points || selected?.routePoints || [];
  if (!selected || !routePoints.length || !appState.visibleLayers.route) return;
  if (appState.selectedId && normalizeVehicleId(selected.asset_id) !== normalizeVehicleId(appState.selectedId)) return;

  const route = document.createElementNS(SVG_NS, "polyline");
  route.setAttribute("points", routeCoordinatePoints(routePoints));
  route.setAttribute("class", `route-path planned ${String(selected.vehicle_type || "").toLowerCase()}`);
  route.setAttribute("opacity", "0.96");
  refs.routeLayer.appendChild(route);
}

function renderMap() {
  renderRiskZones();
  renderWaypointNodes();
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

  renderSelectedPlannerRoute();

  renderHeadquarters();

  refs.mapStage.classList.toggle("awaiting-fleet", !appState.assets.length);
}

function renderHeadquarters() {
  const [x, y] = projectGeoCoordinate(HEADQUARTERS.lon, HEADQUARTERS.lat, appState.mapBbox);
  if (!Number.isFinite(x) || !Number.isFinite(y)) return;

  const markerGroup = document.createElementNS(SVG_NS, "g");
  markerGroup.setAttribute("class", "headquarters-marker");
  markerGroup.setAttribute("aria-label", `${HEADQUARTERS.name} · ${HEADQUARTERS.address}`);

  const title = document.createElementNS(SVG_NS, "title");
  title.textContent = `${HEADQUARTERS.name} · ${HEADQUARTERS.address}`;

  const halo = document.createElementNS(SVG_NS, "circle");
  halo.setAttribute("class", "headquarters-halo");
  halo.setAttribute("cx", x);
  halo.setAttribute("cy", y);
  halo.setAttribute("r", "18");

  const body = document.createElementNS(SVG_NS, "path");
  body.setAttribute("class", "headquarters-body");
  body.setAttribute("d", [
    `M ${x.toFixed(2)} ${(y - 13).toFixed(2)}`,
    `L ${(x + 13).toFixed(2)} ${y.toFixed(2)}`,
    `L ${x.toFixed(2)} ${(y + 13).toFixed(2)}`,
    `L ${(x - 13).toFixed(2)} ${y.toFixed(2)}`,
    "Z"
  ].join(" "));

  const core = document.createElementNS(SVG_NS, "circle");
  core.setAttribute("class", "headquarters-core");
  core.setAttribute("cx", x);
  core.setAttribute("cy", y);
  core.setAttribute("r", "5");

  const label = document.createElementNS(SVG_NS, "text");
  label.setAttribute("class", "headquarters-label");
  label.setAttribute("x", x + 17);
  label.setAttribute("y", y - 15);
  label.textContent = HEADQUARTERS.name;

  markerGroup.append(title, halo, body, core, label);
  refs.vehicleLayer.appendChild(markerGroup);
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

function renderAssetTypeFilters() {
  document.querySelectorAll(".asset-type-filter").forEach((button) => {
    button.classList.toggle("active", appState.assetTypeFilters[button.dataset.type] !== false);
  });
}

function alertSeverityRank(severity) {
  return { RED: 3, AMBER: 2, GREEN: 1 }[severity] || 0;
}

function alertDeviceKey(vehicleId) {
  return normalizeVehicleId(vehicleId);
}

function compareAlerts(a, b) {
  const severityDelta = alertSeverityRank(b.severity) - alertSeverityRank(a.severity);
  if (severityDelta !== 0) return severityDelta;
  return (b.updatedAt || 0) - (a.updatedAt || 0);
}

function sortAlerts() {
  appState.alerts.sort(compareAlerts);
}

function renderAlerts() {
  const visibleAlerts = appState.alerts
    .filter((alert) => appState.activeFilter === "ALL" || alert.severity === appState.activeFilter)
    .sort(compareAlerts);
  refs.alertList.innerHTML = "";

  if (!visibleAlerts.length) {
    refs.alertList.innerHTML = `<div class="empty-state">No live alerts.<br />Waiting for <code>/c2/alerts</code>.</div>`;
  } else {
    visibleAlerts.forEach((alert) => {
      const alertCard = document.createElement("button");
      alertCard.className = `alert-card ${alert.severity}`;
      alertCard.innerHTML = `
        <div class="alert-top-row">
          <span class="alert-level">${alertLabel(alert.severity)} · ${alert.vehicleId.replace("_", "-")}</span>
          <span class="alert-time">${alert.time}</span>
        </div>
        <p class="alert-title">${alert.title}</p>
        <p class="alert-recommendation"><strong>AI:</strong> ${alert.recommendation}</p>
      `;
      alertCard.addEventListener("click", () => {
        selectAssetByVehicleId(alert.vehicleId);
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
  const selectedDestinationValue = refs.operationAreaSelect ? refs.operationAreaSelect.value : "";
  const selectedNodeId = selectedDestinationValue.startsWith("node:")
    ? selectedDestinationValue.slice(5)
    : null;
  const selectedAreaIndex = selectedDestinationValue.startsWith("area:")
    ? Number(selectedDestinationValue.slice(5))
    : -1;
  const selectedNode = selectedNodeId
    ? appState.mapNodes.find((node) => node.id === selectedNodeId)
    : null;
  const selectedArea = command === "MOVE_TO"
    ? selectedNode || appState.operationAreas[selectedAreaIndex]
    : null;

  if (command === "MOVE_TO" && !selectedArea) {
    addAutopilotLog("warning", now, "MOVE_TO ignored: no destination node selected.");
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
    if (selectedNode) {
      payload.target_node_id = selectedNode.id;
      payload.vehicle_type = asset.type;
    }
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
  if (command === "MOVE_TO" && selectedNode) {
    appState.selectedRoute = null;
    appState.routeCandidates = [];
    publishRos(APP_CONFIG.topics.plannerRequest, {
      schema: "missiondeck.planner.request.v1",
      request_id: `REQ_${Date.now()}`,
      vehicle_id: asset.id,
      asset_id: asset.id,
      target_node_id: selectedNode.id,
      vehicle_type: asset.type,
      selected_category: asset.type,
      source: "WEB_C2",
      requested_at: new Date().toISOString()
    });
  }
  renderAll();
}

function addAutopilotLog(type, time, text) {
  appState.autopilotLogs.unshift({ type, time, text });
}

function overrideForVehicle(vehicleId) {
  return appState.alertOverrides[normalizeVehicleId(vehicleId)] || null;
}

function applyOverrideToAsset(asset) {
  const override = overrideForVehicle(asset.id);
  if (!override) return asset;

  asset.alert = override.severity || asset.alert;
  asset.cameraMode = override.cameraMode || asset.cameraMode;
  asset.cameraStatus = override.cameraStatus || asset.cameraStatus;
  asset.missionState = override.missionState || asset.missionState;
  if (asset.uxvState) {
    asset.uxvState.device_state = override.deviceState || asset.uxvState.device_state;
    asset.uxvState.mission_status = override.missionStatus || asset.uxvState.mission_status;
  }
  return asset;
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
  const uxvState = {
    id: raw.id || (raw.vehicle_id ? raw.vehicle_id.replace(/_/g, "-") : "UNKNOWN"),
    type: raw.type || raw.vehicle_type || type,
    battery: Number(raw.battery ?? raw.battery_pct ?? 0),
    comm_quality: Number(raw.comm_quality ?? raw.link_quality ?? 0),
    device_state: raw.device_state || "unknown",
    mission_status: raw.mission_status || raw.mission_state || raw.status || "unknown",
    speed_mps: Number(raw.speed_mps ?? raw.speed ?? 0),
    assignment_possible: Boolean(raw.assignment_possible ?? raw.assignable),
    position: { lat, lon }
  };

  return applyOverrideToAsset({
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
    route: Array.isArray(raw.route) ? raw.route : [],
    uxvState
  });
}

function handleFleetPayload(data) {
  const incomingAssets = Array.isArray(data) ? data : (data.assets || []);
  const nextMapBbox = getFleetFitBbox(incomingAssets);
  const shouldRedrawMap = bboxChanged(appState.mapBbox, nextMapBbox);

  appState.mapBbox = nextMapBbox;
  if (shouldRedrawMap && appState.geoJsonData) {
    renderGeoJson(appState.geoJsonData, nextMapBbox);
  }

  appState.assets = incomingAssets
    .map(normalizeAsset)
    .filter(asset => asset.id);

  ensureSelectedAsset();
  renderAll();
}

function handleRouteCandidatesPayload(data) {
  const candidates = Array.isArray(data) ? data : (data.candidates || []);
  appState.routeCandidates = candidates;
  const feasible = candidates.filter((candidate) => candidate.feasible);
  if (!feasible.length) return;
  const best = feasible.reduce((winner, candidate) => (
    Number(candidate.total_cost) < Number(winner.total_cost) ? candidate : winner
  ), feasible[0]);
  appState.autopilotLogs.unshift({
    type: "auto",
    time: getKstTime(),
    text: `Cost comparison: ${feasible.length}/${candidates.length} feasible, lowest ${best.asset_id} cost ${Number(best.total_cost).toFixed(1)}.`
  });
}

function handleSelectedRoutePayload(data) {
  const raw = Array.isArray(data) ? data[0] : data;
  if (!raw) return;

  appState.selectedRoute = raw;
  const selected = raw.selected;
  if (!selected) {
    appState.autopilotLogs.unshift({
      type: "warning",
      time: getKstTime(),
      text: `Planner returned no feasible route: ${raw.reason || "unknown reason"}.`
    });
    renderAll();
    return;
  }

  selectAssetByVehicleId(selected.asset_id);
  appState.missionLogs.unshift({
    type: "auto",
    time: getKstTime(),
    text: `Best route: ${selected.asset_id} -> ${selected.target_node_id}, cost ${Number(selected.total_cost).toFixed(1)}, distance ${Number(selected.distance_km).toFixed(1)} km.`
  });
  renderAll();
}

function findAssetByVehicleId(vehicleId) {
  const target = normalizeVehicleId(vehicleId);
  return appState.assets.find((asset) => normalizeVehicleId(asset.id) === target) || null;
}

function selectAssetByVehicleId(vehicleId) {
  const asset = findAssetByVehicleId(vehicleId);
  if (asset) {
    appState.assetTypeFilters[asset.type] = true;
  }
  appState.selectedId = asset ? asset.id : vehicleId;
}

function isVisionAlert(raw) {
  const markerText = [
    raw.schema,
    raw.alert_id,
    raw.source,
    raw.reason,
    raw.title,
    raw.camera_mode
  ].filter(Boolean).join(" ");
  return Array.isArray(raw.detections) || /YOLO|VISION/i.test(markerText);
}

function applyAlertToAsset(raw, severity) {
  const vehicleId = raw.vehicle_id || raw.vehicleId;
  const key = normalizeVehicleId(vehicleId);
  if (!key) return;

  const asset = findAssetByVehicleId(vehicleId);
  if (severity !== "RED") {
    delete appState.alertOverrides[key];
    if (asset) {
      asset.alert = severity;
    }
    return;
  }
  if (!isVisionAlert(raw)) {
    if (asset) {
      asset.alert = severity;
    }
    return;
  }

  const override = {
    enemySpotted: true,
    cameraMode: raw.camera_mode || "EO / YOLO TRACK",
    cameraStatus: raw.camera_status || raw.reason || raw.title || "RED alert received",
    missionState: raw.mission_state || "TRACKING",
    missionStatus: "YOLO_DETECTED",
    updatedAt: Date.now()
  };
  appState.alertOverrides[key] = override;

  if (!asset) return;

  asset.cameraMode = override.cameraMode;
  asset.cameraStatus = override.cameraStatus;
  asset.missionState = override.missionState;
  if (asset.uxvState) {
    asset.uxvState.mission_status = override.missionStatus;
  }
}

function handleAlertPayload(data) {
  const raw = Array.isArray(data) ? data[0] : data;
  if (!raw) return;
  const severity = raw.severity || raw.alert_level || "AMBER";
  applyAlertToAsset(raw, severity);
  const vehicleId = raw.vehicle_id || raw.vehicleId || "UNKNOWN";
  const key = alertDeviceKey(vehicleId);

  appState.alerts = appState.alerts.filter((alert) => (alert.key || alertDeviceKey(alert.vehicleId)) !== key);
  if (severity === "GREEN") {
    renderAll();
    return;
  }

  const nextAlert = {
    id: raw.alert_id || `ALERT_${Date.now()}`,
    vehicleId,
    severity,
    title: raw.reason || raw.title || "Live alert received",
    recommendation: raw.recommended_action || raw.recommendation || "Review required.",
    time: raw.time || getKstTime(),
    updatedAt: Date.now(),
    key
  };
  appState.alerts.push(nextAlert);
  sortAlerts();
  appState.alerts = appState.alerts.slice(0, 50);
  renderAll();
}

function handleVisionDetectionsPayload(data) {
  const raw = Array.isArray(data) ? data[0] : data;
  if (!raw) return;

  const vehicleId = raw.vehicle_id || raw.vehicleId || "UAV-1";
  const detections = Array.isArray(raw.detections) ? raw.detections : [];
  appState.vision.lastDetectionAt = Date.now();

  if (!appState.vision.active || normalizeVehicleId(vehicleId) !== normalizeVehicleId(appState.vision.activeAssetId)) {
    return;
  }

  const asset = findAssetByVehicleId(vehicleId);
  appState.vision.backendOnline = true;
  appState.vision.detections = detections;
  const cameraStatus = detections.length
    ? `YOLO topic · ${detections.length} object(s) tracked`
    : "YOLO topic · no object detected";
  if (asset) {
    asset.cameraMode = "EO / YOLO TRACK";
    asset.cameraStatus = cameraStatus;
  }
  refs.cameraStatus.textContent = cameraStatus;
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
    resetLiveData();
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
      .filter(topic => ![APP_CONFIG.topics.operatorCommand, APP_CONFIG.topics.plannerRequest].includes(topic))
      .forEach(subscribeRos);
  };

  rosSocket.onclose = () => {
    rosSocket = null;
    resetLiveData();
  };
  rosSocket.onerror = () => resetLiveData("ROS ERROR · ROSBRIDGE NOT AVAILABLE");

  rosSocket.onmessage = (event) => {
    let message;
    try { message = JSON.parse(event.data); } catch { return; }
    if (message.op !== "publish") return;

    const data = decodeRosData(message.msg);
    switch (message.topic) {
      case APP_CONFIG.topics.fleetState:
        handleFleetPayload(data);
        break;
      case APP_CONFIG.topics.waypointNodes:
        handleWaypointNodesPayload(data);
        break;
      case APP_CONFIG.topics.riskZones:
        handleRiskZonesPayload(data);
        break;
      case APP_CONFIG.topics.routeCandidates:
        handleRouteCandidatesPayload(data);
        break;
      case APP_CONFIG.topics.selectedRoute:
        handleSelectedRoutePayload(data);
        break;
      case APP_CONFIG.topics.alerts:
        handleAlertPayload(data);
        break;
      case APP_CONFIG.topics.visionDetections:
        handleVisionDetectionsPayload(data);
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
      id: "UAV_02", type: "UAV", subtype: "Multicopter", icon: "✈", role: "Target confirmation",
      battery: 44, link: 78, speed: 14.2, navConfidence: 81, assignable: true,
      alert: "AMBER", missionState: "STANDBY", mission: "Standby · Target reacquisition",
      cameraMode: "EO / IR LIVE", cameraStatus: "Demo telemetry", lat: 37.5625, lon: 127.0039,
      alt: 120, x: 574, y: 333, route: []
    },
    {
      id: "UGV_01", type: "UGV", subtype: "Rover", icon: "🚗", role: "Ground investigation",
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
  ].map((alert, index) => ({
    ...alert,
    key: alertDeviceKey(alert.vehicleId),
    updatedAt: Date.now() - index
  }));
  sortAlerts();
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
  document.querySelectorAll(".asset-type-filter").forEach((button) => {
    button.addEventListener("click", () => {
      const type = button.dataset.type;
      appState.assetTypeFilters[type] = appState.assetTypeFilters[type] === false;
      ensureSelectedAsset();
      renderAll();
    });
  });

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
  renderOperationAreaOptions();
  renderEquipmentList();
  renderAssetTypeFilters();
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
initializeVisionAssets();

if (APP_CONFIG.demoMode) {
  enableDemoData();
}

renderAll();
setInterval(updateClock, 1000);
