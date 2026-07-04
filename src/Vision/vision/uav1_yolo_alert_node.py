#!/usr/bin/env python3

import json
import os
import time
from pathlib import Path

os.environ.setdefault("YOLO_CONFIG_DIR", "/tmp/Ultralytics")

try:
    import cv2
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import String
    from ultralytics import YOLO
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Required Python modules are not available in this terminal.\n"
        "Source ROS 2 and install vision dependencies first:\n\n"
        "  source /opt/ros/humble/setup.bash\n"
        "  python3 -m pip install ultralytics opencv-python\n"
        "  source /home/kuzdx/d4d_ws/install/setup.bash\n"
        "  ros2 run vision uav1_yolo_alert_node\n"
    ) from exc


def find_workspace_resource(filename: str) -> str:
    for base in (Path.cwd(), *Path(__file__).resolve().parents):
        candidate = base / "res" / filename
        if candidate.exists():
            return str(candidate)
    return str(Path.cwd() / "res" / filename)


DEFAULT_MODEL_PATH = find_workspace_resource("best.pt")
DEFAULT_VIDEO_PATH = find_workspace_resource("uav1.webm")


class Uav1YoloAlertNode(Node):
    def __init__(self):
        super().__init__("uav1_yolo_alert_node")

        self.declare_parameter("vehicle_id", "UAV-1")
        self.declare_parameter("model_path", DEFAULT_MODEL_PATH)
        self.declare_parameter("video_path", DEFAULT_VIDEO_PATH)
        self.declare_parameter("confidence", 0.25)
        self.declare_parameter("publish_hz", 6.0)
        self.declare_parameter("alert_cooldown_sec", 6.0)

        self.vehicle_id = str(self.get_parameter("vehicle_id").value)
        self.model_path = Path(str(self.get_parameter("model_path").value)).expanduser()
        self.video_path = Path(str(self.get_parameter("video_path").value)).expanduser()
        self.confidence = float(self.get_parameter("confidence").value)
        publish_hz = max(0.5, float(self.get_parameter("publish_hz").value))
        self.alert_cooldown_sec = max(0.0, float(self.get_parameter("alert_cooldown_sec").value))

        if not self.model_path.exists():
            raise RuntimeError(f"YOLO model file not found: {self.model_path}")
        if not self.video_path.exists():
            raise RuntimeError(f"UAV1 video file not found: {self.video_path}")

        self.model = YOLO(str(self.model_path))
        self.capture = cv2.VideoCapture(str(self.video_path))
        if not self.capture.isOpened():
            raise RuntimeError(f"Cannot open UAV1 video: {self.video_path}")

        self.frame_index = 0
        self.last_alert_time = 0.0
        self.detection_publisher = self.create_publisher(String, "/c2/vision/uav1/detections", 10)
        self.alert_publisher = self.create_publisher(String, "/c2/alerts", 10)
        self.autopilot_log_publisher = self.create_publisher(String, "/c2/autopilot_log", 10)

        self.create_timer(1.0 / publish_hz, self.on_timer)
        self.get_logger().info(
            "UAV1 YOLO node ready: "
            f"vehicle_id={self.vehicle_id}, model={self.model_path}, video={self.video_path}, "
            f"publish_hz={publish_hz:.2f}, confidence={self.confidence:.2f}"
        )

    def read_frame(self):
        ok, frame = self.capture.read()
        if ok and frame is not None:
            self.frame_index += 1
            return frame

        self.capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
        self.frame_index = 0
        ok, frame = self.capture.read()
        if not ok or frame is None:
            raise RuntimeError(f"Cannot read frame from UAV1 video: {self.video_path}")
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
            detections = self.detect(frame)
        except Exception as exc:
            self.get_logger().error(f"UAV1 YOLO detection failed: {exc}")
            return

        height, width = frame.shape[:2]
        payload = {
            "schema": "c2.vision.detections.v1",
            "vehicle_id": self.vehicle_id,
            "source": "uav1_yolo_alert_node",
            "model": self.model_path.name,
            "video": self.video_path.name,
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
        recommendation = "Classify target, maintain visual track, and escalate UAV1 operator review."
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
        if hasattr(self, "capture"):
            self.capture.release()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = Uav1YoloAlertNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
