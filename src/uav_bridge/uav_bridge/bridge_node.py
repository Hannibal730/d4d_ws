import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from vision_msgs.msg import Detection2DArray, Detection2D, ObjectHypothesisWithPose
import zmq
import json

class ZMQToROS2Bridge(Node):
    def __init__(self):
        super().__init__('zmq_ros2_bridge')
        
        # 1. ZMQ 수신 소켓 설정 (포트 5555번 개방, 모든 IP 수용)
        context = zmq.Context()
        self.socket = context.socket(zmq.SUB)
        self.socket.bind("tcp://0.0.0.0:5555") 
        self.socket.setsockopt_string(zmq.SUBSCRIBE, "")
        
        # 2. ROS2 토픽 Publisher 생성
        self.img_pub = self.create_publisher(CompressedImage, '/uav/image/compressed', 10)
        self.bbox_pub = self.create_publisher(Detection2DArray, '/uav/detections', 10)
        
        # 3. 아주 빠른 속도(1ms)로 버퍼를 확인하는 타이머 루프
        self.timer = self.create_timer(0.001, self.receive_data) 
        self.get_logger().info("ZMQ Bridge Node started. Listening on port 5555...")

    def receive_data(self):
        try:
            # 블로킹(멈춤) 없이 데이터가 들어왔을 때만 즉시 낚아챔
            msg = self.socket.recv_multipart(flags=zmq.NOBLOCK)
            
            # 메타데이터(바운딩 박스)와 영상 바이너리 분리
            metadata_json = msg[0].decode('utf-8')
            image_bytes = msg[1]
            
            metadata = json.loads(metadata_json)
            
            # 기준이 되는 타임스탬프 (영상과 바운딩 박스를 동기화하기 위해 동일한 시간 부여)
            current_time = self.get_clock().now().to_msg()
            frame_id = "uav_camera_link"
            
            # ----------------------------------------------------
            # 1. 압축 영상 (CompressedImage) 토픽 구성
            # ----------------------------------------------------
            ros_img = CompressedImage()
            ros_img.header.stamp = current_time
            ros_img.header.frame_id = frame_id
            ros_img.format = "jpeg"
            ros_img.data = list(image_bytes) # 바이너리를 ROS2 통신 규격에 맞게 리스트화
            
            # ----------------------------------------------------
            # 2. 디텍션 (Detection2DArray) 토픽 구성
            # ----------------------------------------------------
            ros_bbox = Detection2DArray()
            ros_bbox.header.stamp = current_time
            ros_bbox.header.frame_id = frame_id
            
            for det in metadata['detections']:
                x1, y1, x2, y2 = det['bbox']
                
                # ROS2 표준에 맞게 [중심점x, 중심점y, 너비, 높이] 로 수학적 변환
                width = float(x2 - x1)
                height = float(y2 - y1)
                center_x = float(x1 + width / 2.0)
                center_y = float(y1 + height / 2.0)
                
                detection_msg = Detection2D()
                
                # 바운딩 박스 좌표 입력
                detection_msg.bbox.center.position.x = center_x
                detection_msg.bbox.center.position.y = center_y
                detection_msg.bbox.size_x = width
                detection_msg.bbox.size_y = height
                
                # 클래스(이름)와 신뢰도(Confidence) 입력
                hypothesis = ObjectHypothesisWithPose()
                hypothesis.hypothesis.class_id = det['class']
                hypothesis.hypothesis.score = float(det['conf'])
                
                detection_msg.results.append(hypothesis)
                ros_bbox.detections.append(detection_msg)
            
            # 3. 토픽 동시 발행 (Publish)
            self.img_pub.publish(ros_img)
            self.bbox_pub.publish(ros_bbox)
            
            # 수신 여부를 터미널에 간단히 표기 (로그 도배 방지를 위해 10개 프레임에 한 번씩 출력하는 등 응용 가능)
            # self.get_logger().info(f"Published Image & {len(metadata['detections'])} Detections.")
                
        except zmq.Again:
            pass # 큐에 데이터가 없으면 대기 없이 스킵 (다음 프레임으로)

def main(args=None):
    rclpy.init(args=args)
    node = ZMQToROS2Bridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Bridge Node stopped by user.")
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()