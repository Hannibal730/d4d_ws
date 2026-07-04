# AEGIS ONE · Multi-UxV Control Center — Live Data First

## Important behavior

This version **does not display any aircraft, UGV, USV, path, alert, or moving asset by default**.

The UI stays in:

```text
ROS OFFLINE · WAITING FOR FLEET STATE
```

until ROS Main Core publishes a normalized fleet-state message.

This is intentional. The browser is now a **live C2 display**, not an autonomous fake simulator.

---

## Files

```text
index.html
style.css
app.js
README.md
```

## Run

```bash
cd uxv_c2_control_center_live_v3
python3 -m http.server 8080
```

Open:

```text
http://127.0.0.1:8080
```

## Optional visual-only demo mode

Only for UI presentation without devices:

```text
http://127.0.0.1:8080/?demo=1
```

`?demo=1` is explicitly marked as **DEMO MODE** in the header.

---

## ROSBridge connection

1. Start ROS bridge:

```bash
sudo apt install ros-humble-rosbridge-suite
ros2 launch rosbridge_server rosbridge_websocket_launch.xml
```

2. Press **Connect ROS** in the web UI.

The browser connects to:

```text
ws://127.0.0.1:9090
```

## Expected normalized topics

```text
/c2/fleet/state       std_msgs/msg/String(JSON)
/c2/alerts            std_msgs/msg/String(JSON)
/c2/autopilot_log     std_msgs/msg/String(JSON)
/c2/mission_log       std_msgs/msg/String(JSON)
/c2/operator_command  std_msgs/msg/String(JSON)
```

### Fleet state payload

```json
{
  "assets": [
    {
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
      "route": [[548,171],[520,212],[493,254]]
    }
  ]
}
```

## Architecture

```text
PX4 / ArduPilot / UGV-USV Digital Twin
                ↓
            ROS 2 Main Core
                ↓
       rosbridge_websocket :9090
                ↓
      Live Web C2 (this application)
```

The UI must never generate synthetic vehicle state in production mode.
