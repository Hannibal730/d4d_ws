#!/usr/bin/env python3

import json
import os
import sys
import time
import types
from pathlib import Path

os.environ.setdefault("YOLO_CONFIG_DIR", "/tmp/Ultralytics")


def disable_matplotlib_import_for_yolo():
    """Ultralytics imports plotting modules even for detection-only inference."""
    if "matplotlib" in sys.modules:
        return
    matplotlib_stub = types.ModuleType("matplotlib")
    pyplot_stub = types.ModuleType("matplotlib.pyplot")
    matplotlib_stub.pyplot = pyplot_stub
    sys.modules["matplotlib"] = matplotlib_stub
    sys.modules["matplotlib.pyplot"] = pyplot_stub


disable_matplotlib_import_for_yolo()

try:
    import cv2
    import numpy as np
    import rclpy
    from sensor_msgs.msg import CompressedImage
    from rclpy.node import Node
    from std_msgs.msg import String
    from ultralytics import YOLO
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Required Python modules are not available in this terminal.\n"
        "Source ROS 2 and install vision dependencies first:\n\n"
        "  source /opt/ros/humble/setup.bash\n"
        "  python3 -m pip install ultralytics opencv-python\n"
        "  source /home/hannibal/d4d_ws/install/setup.bash\n"
        "  ros2 run vision uav_yolo_alert_node\n"
    ) from exc


def find_workspace_resource(filename: str) -> str:
    for base in (Path.cwd(), *Path(__file__).resolve().parents):
        candidate = base / "res" / filename
        if candidate.exists():
            return str(candidate)
    return str(Path.cwd() / "res" / filename)


DEFAULT_MODEL_PATH = find_workspace_resource("best.pt")
DEFAULT_VIDEO_PATH = find_workspace_resource("uav1.webm")


def normalize_vehicle_topic_id(vehicle_id: str) -> str:
    return "".join(ch for ch in str(vehicle_id or "").lower() if ch.isalnum())


def sanitize_ros_topic(topic: str) -> str:
    return str(topic or "").replace("-", "_")


class UavYoloAlertNode(Node):
    def __init__(self):
        super().__init__("uav_yolo_alert_node")

        self.declare_parameter("vehicle_id", "UAV-1")
        self.declare_parameter("model_path", DEFAULT_MODEL_PATH)
        self.declare_parameter("video_path", DEFAULT_VIDEO_PATH)
        self.declare_parameter("source_type", "file")
        self.declare_parameter("image_topic", "/missiondeck/uxv/UAV_2/video/compressed")
        self.declare_parameter("detection_topic", "")
        self.declare_parameter("confidence", 0.25)
        self.declare_parameter("publish_hz", 6.0)
        self.declare_parameter("alert_cooldown_sec", 6.0)

        self.vehicle_id = str(self.get_parameter("vehicle_id").value)
        self.model_path = Path(str(self.get_parameter("model_path").value)).expanduser()
        self.video_path = Path(str(self.get_parameter("video_path").value)).expanduser()
        self.source_type = str(self.get_parameter("source_type").value).lower()
        raw_image_topic = str(self.get_parameter("image_topic").value)
        self.image_topic = sanitize_ros_topic(raw_image_topic)
        detection_topic = str(self.get_parameter("detection_topic").value).strip()
        if not detection_topic:
            detection_topic = f"/c2/vision/{normalize_vehicle_topic_id(self.vehicle_id)}/detections"
        detection_topic = sanitize_ros_topic(detection_topic)
        self.confidence = float(self.get_parameter("confidence").value)
        publish_hz = max(0.5, float(self.get_parameter("publish_hz").value))
        self.alert_cooldown_sec = max(0.0, float(self.get_parameter("alert_cooldown_sec").value))

        if not self.model_path.exists():
            raise RuntimeError(f"YOLO model file not found: {self.model_path}")
        if self.image_topic != raw_image_topic:
            self.get_logger().warning(
                f"Sanitized image_topic from {raw_image_topic} to {self.image_topic}"
            )

        self.model = YOLO(str(self.model_path))
        self.capture = None
        self.latest_frame = None
        self.latest_frame_stamp = 0.0
        if self.source_type == "topic":
            self.create_subscription(CompressedImage, self.image_topic, self.on_compressed_image, 10)
        else:
            if not self.video_path.exists():
                raise RuntimeError(f"Video file not found: {self.video_path}")
            self.capture = cv2.VideoCapture(str(self.video_path))
            if not self.capture.isOpened():
                raise RuntimeError(f"Cannot open video: {self.video_path}")

        self.frame_index = 0
        self.last_alert_time = 0.0
        self.detection_publisher = self.create_publisher(String, detection_topic, 10)
        self.alert_publisher = self.create_publisher(String, "/c2/alerts", 10)
        self.autopilot_log_publisher = self.create_publisher(String, "/c2/autopilot_log", 10)

        self.create_timer(1.0 / publish_hz, self.on_timer)
        self.get_logger().info(
            "UAV YOLO node ready: "
            f"vehicle_id={self.vehicle_id}, source_type={self.source_type}, "
            f"image_topic={self.image_topic}, detection_topic={detection_topic}, "
            f"model={self.model_path}, video={self.video_path if self.capture else 'disabled'}, "
            f"publish_hz={publish_hz:.2f}, confidence={self.confidence:.2f}"
        )

    def on_compressed_image(self, msg: CompressedImage):
        frame = cv2.imdecode(np.frombuffer(msg.data, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            self.get_logger().warning(f"Dropping {self.vehicle_id} frame: compressed image decode failed")
            return
        self.latest_frame = frame
        self.latest_frame_stamp = time.time()

    def read_frame(self):
        if self.source_type == "topic":
            if self.latest_frame is None:
                return None
            self.frame_index += 1
            return self.latest_frame.copy()

        ok, frame = self.capture.read()
        if ok and frame is not None:
            self.frame_index += 1
            return frame

        self.capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
        self.frame_index = 0
        ok, frame = self.capture.read()
        if not ok or frame is None:
            raise RuntimeError(f"Cannot read frame from video: {self.video_path}")
        self.frame_index += 1
        return frame

    def detect(self, frame):
        result = self.model(frame, verbose=False, conf=self.confidence)[0]
        names = result.names or {}
        detections = []

        for box in result.boxes:
            class_id = int(box.cls[0].item())
            x1, y1, x2, y2 = [float(value) for value in box.xyxy[0].tolist()]
            detections.append({
                "label": names.get(class_id, str(class_id)),
                "class_id": class_id,
                "confidence": float(box.conf[0].item()),
                "bbox": [x1, y1, x2, y2],
            })

        return detections

    def on_timer(self):
        try:
            frame = self.read_frame()
            if frame is None:
                return
            detections = self.detect(frame)
        except Exception as exc:
            self.get_logger().error(f"{self.vehicle_id} YOLO detection failed: {exc}")
            return

        height, width = frame.shape[:2]
        payload = {
            "schema": "c2.vision.detections.v1",
            "vehicle_id": self.vehicle_id,
            "source": "uav_yolo_alert_node",
            "model": self.model_path.name,
            "source_type": self.source_type,
            "video": self.video_path.name if self.capture else None,
            "image_topic": self.image_topic if self.source_type == "topic" else None,
            "frame_index": self.frame_index,
            "frame_size": [width, height],
            "detections": detections,
            "stamp": time.time(),
        }
        self.detection_publisher.publish(String(data=json.dumps(payload, separators=(",", ":"))))

        if detections:
            self.publish_red_alert(detections)

    def publish_red_alert(self, detections):
        now = time.time()
        if now - self.last_alert_time < self.alert_cooldown_sec:
            return

        self.last_alert_time = now
        labels = sorted({detection["label"] for detection in detections})
        confidence = max(float(detection["confidence"]) for detection in detections)
        title = f"YOLO object detected: {', '.join(labels)}"
        recommendation = f"Classify target, maintain visual track, and escalate {self.vehicle_id} operator review."
        payload = {
            "schema": "c2.alert.v1",
            "alert_id": f"VISION_{self.vehicle_id}_{int(now * 1000)}",
            "vehicle_id": self.vehicle_id,
            "severity": "RED",
            "alert_level": "RED",
            "reason": title,
            "title": title,
            "recommended_action": recommendation,
            "recommendation": recommendation,
            "camera_mode": "EO / YOLO TRACK",
            "camera_status": f"YOLO RED alert - {len(detections)} object(s) tracked",
            "mission_state": "TRACKING",
            "mission_status": "YOLO_DETECTED",
            "confidence": confidence,
            "detections": detections,
        }
        self.alert_publisher.publish(String(data=json.dumps(payload, separators=(",", ":"))))
        self.autopilot_log_publisher.publish(String(data=json.dumps({
            "type": "critical",
            "text": f"{self.vehicle_id} YOLO RED alert published to /c2/alerts: {title}",
        }, separators=(",", ":"))))
        self.get_logger().warning(f"{self.vehicle_id} RED alert published: {title}")

    def destroy_node(self):
        if getattr(self, "capture", None) is not None:
            self.capture.release()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = UavYoloAlertNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
