#!/usr/bin/env python3

from vision.uav1_yolo_alert_node import DEFAULT_UAV2_IMAGE_TOPIC, run_node


def main(args=None):
    run_node(
        args=args,
        node_name="uav2_yolo_alert_node",
        default_vehicle_id="UAV-2",
        default_source_type="topic",
        default_image_topic=DEFAULT_UAV2_IMAGE_TOPIC,
    )


if __name__ == "__main__":
    main()
