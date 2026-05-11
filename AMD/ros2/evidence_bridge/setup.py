from setuptools import find_packages, setup

setup(
    name="evidence_bridge",
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    install_requires=["setuptools", "requests"],
    data_files=[
        ("share/evidence_bridge/launch", ["launch/bridge.launch.py"]),
    ],
    entry_points={
        "console_scripts": [
            "bridge_node = evidence_bridge.bridge_node:main",
            "gas_leak_publisher = evidence_bridge.gas_leak_publisher:main",
        ],
    },
)
