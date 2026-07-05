from setuptools import find_packages, setup


package_name = "vision"


setup(
    name=package_name,
    version="0.0.1",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="hannibal",
    maintainer_email="hannibal@example.com",
    description="UAV YOLO vision node for CoreCenter alerts.",
    license="MIT",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "uav1_yolo_alert_node = vision.uav1_yolo_alert_node:main",
            "uav_yolo_alert_node = vision.uav1_yolo_alert_node:main",
            "uav2_yolo_alert_node = vision.uav2_yolo_alert_node:main",  # <--- 이 줄을 추가해 주세요!
        ],
    },
)
