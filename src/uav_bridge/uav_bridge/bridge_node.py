#!/usr/bin/env python3

import base64
import json
import time

try:
    import cv2
    import numpy as np
    import rclpy
    import zmq
    from rclpy.node import Node
    from sensor_msgs.msg import CompressedImage
    from std_msgs.msg import String
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Required modules are not available.\n"
        "Source ROS 2 and install bridge dependencies first:\n\n"
        "  source /opt/ros/humble/setup.bash\n"
        "  python3 -m pip install pyzmq opencv-python numpy\n"
        "  source /home/hannibal/d4d_ws/install/setup.bash\n"
        "  ros2 run uav_bridge bridge_node\n"
    ) from exc


def sanitize_ros_topic(topic: str) -> str:
    return str(topic or "").replace("-", "_")


class ZmqVideoBridgeNode(Node):
    def __init__(self):
        super().__init__("uav2_zmq_video_bridge")

        self.declare_parameter("bind_address", "tcp://0.0.0.0:5555")
        self.declare_parameter("vehicle_id", "UAV-2")
        self.declare_parameter("output_topic", "/missiondeck/uxv/UAV_2/video/compressed")
        self.declare_parameter("ui_frame_topic", "/c2/vision/uav2/frame")
        self.declare_parameter("ui_frame_hz", 10.0)
        self.declare_parameter("poll_hz", 60.0)
        self.declare_parameter("validate_jpeg", True)
        self.declare_parameter("show_preview", False)

        self.bind_address = str(self.get_parameter("bind_address").value)
        self.vehicle_id = str(self.get_parameter("vehicle_id").value)
        raw_output_topic = str(self.get_parameter("output_topic").value)
        raw_ui_frame_topic = str(self.get_parameter("ui_frame_topic").value)
        self.output_topic = sanitize_ros_topic(raw_output_topic)
        self.ui_frame_topic = sanitize_ros_topic(raw_ui_frame_topic)
        if self.output_topic != raw_output_topic:
            self.get_logger().warning(
                f"Sanitized output_topic from {raw_output_topic} to {self.output_topic}"
            )
        if self.ui_frame_topic != raw_ui_frame_topic:
            self.get_logger().warning(
                f"Sanitized ui_frame_topic from {raw_ui_frame_topic} to {self.ui_frame_topic}"
            )
        self.ui_frame_hz = max(0.1, float(self.get_parameter("ui_frame_hz").value))
        self.validate_jpeg = bool(self.get_parameter("validate_jpeg").value)
        self.show_preview = bool(self.get_parameter("show_preview").value)
        poll_hz = max(1.0, float(self.get_parameter("poll_hz").value))

        self.zmq_context = zmq.Context()
        self.socket = self.zmq_context.socket(zmq.SUB)
        self.socket.setsockopt_string(zmq.SUBSCRIBE, "")
        self.socket.setsockopt(zmq.RCVHWM, 1)
        self.socket.bind(self.bind_address)

        self.publisher = self.create_publisher(CompressedImage, self.output_topic, 10)
        self.ui_frame_publisher = self.create_publisher(String, self.ui_frame_topic, 10)
        self.frame_count = 0
        self.last_log_time = 0.0
        self.last_ui_frame_time = 0.0

        self.create_timer(1.0 / poll_hz, self.poll_frame)
        self.get_logger().info(
            f"ZMQ video bridge ready: bind={self.bind_address}, vehicle_id={self.vehicle_id}, "
            f"output_topic={self.output_topic}, ui_frame_topic={self.ui_frame_topic}, "
            f"validate_jpeg={self.validate_jpeg}"
        )

    def poll_frame(self) -> None:
        while True:
            try:
                image_bytes = self.socket.recv(flags=zmq.NOBLOCK)
            except zmq.Again:
                return

            if self.validate_jpeg or self.show_preview:
                frame = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
                if frame is None:
                    self.get_logger().warning("Dropping frame: JPEG decode failed")
                    continue
                if self.show_preview:
                    cv2.imshow(f"{self.vehicle_id} ZMQ video bridge", frame)
                    cv2.waitKey(1)

            msg = CompressedImage()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = f"{self.vehicle_id}/camera"
            msg.format = "jpeg"
            msg.data = image_bytes
            self.publisher.publish(msg)

            self.frame_count += 1
            now = time.time()
            if now - self.last_ui_frame_time >= 1.0 / self.ui_frame_hz:
                self.last_ui_frame_time = now
                self.ui_frame_publisher.publish(String(data=json.dumps({
                    "schema": "c2.vision.frame.v1",
                    "vehicle_id": self.vehicle_id,
                    "encoding": "jpeg",
                    "frame_index": self.frame_count,
                    "stamp": now,
                    "data": base64.b64encode(image_bytes).decode("ascii"),
                }, separators=(",", ":"))))
            if now - self.last_log_time >= 5.0:
                self.last_log_time = now
                self.get_logger().info(
                    f"Published {self.frame_count} compressed frame(s) to {self.output_topic}"
                )

    def destroy_node(self):
        if self.show_preview:
            cv2.destroyAllWindows()
        self.socket.close(linger=0)
        self.zmq_context.term()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = ZmqVideoBridgeNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
