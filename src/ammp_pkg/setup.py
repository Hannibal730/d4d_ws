from setuptools import find_packages, setup


package_name = "ammp_pkg"


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
    description="MissionDeck AMMP ROS2 nodes.",
    license="MIT",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "random_uxv_state_spawner = ammp_pkg.random_uxv_state_spawner:main",
            "map_node_publisher = ammp_pkg.map_node_publisher:main",
            "missiondeck_to_c2_bridge = ammp_pkg.missiondeck_to_c2_bridge:main",
        ],
    },
)
