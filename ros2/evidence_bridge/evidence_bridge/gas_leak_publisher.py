"""Gas leak incident publisher.

Publishes a simulated gas concentration ramp on /gas_sensor_0/reading
and wind state on /wind/state.  Used when no real Gazebo gas plugin is
available or during bag replay where sensor topics are pre-recorded.

Run:
    ros2 run evidence_bridge gas_leak_publisher
Or as part of a bag-replay scenario:
    ros2 bag record -o lng_incident /drone_cam/image_raw /cctv_gate/image_raw \
        /gas_sensor_0/reading /wind/state
"""
import json
import math
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32, String


class GasLeakPublisher(Node):
    def __init__(self):
        super().__init__("gas_leak_publisher")
        self._gas_pub = self.create_publisher(Float32, "/gas_sensor_0/reading", 10)
        self._wind_pub = self.create_publisher(String, "/wind/state", 10)
        self._t0 = time.time()
        self.create_timer(1.0, self._tick)
        self.get_logger().info("GasLeakPublisher started — incident ramp begins at t=20s")

    def _tick(self):
        elapsed = time.time() - self._t0

        if elapsed < 20:
            ppm = 2.0 + 0.5 * math.sin(elapsed)
        elif elapsed < 40:
            ppm = 2.0 + (elapsed - 20) * 1.2
        elif elapsed < 70:
            ppm = 26.0 + 3.0 * math.sin(elapsed * 0.3)
        else:
            ppm = max(2.0, 26.0 - (elapsed - 70) * 0.8)

        gas_msg = Float32()
        gas_msg.data = float(ppm)
        self._gas_pub.publish(gas_msg)

        wind_speed = 3.5 + 0.8 * math.sin(elapsed * 0.1)
        wind_dir = 225.0 + 15.0 * math.sin(elapsed * 0.05)
        wind_msg = String()
        wind_msg.data = json.dumps({
            "speed_mps": round(wind_speed, 2),
            "direction_deg": round(wind_dir, 1),
            "timestamp": time.time(),
        })
        self._wind_pub.publish(wind_msg)

        if elapsed % 5 < 1:
            self.get_logger().info(
                f"t={elapsed:.0f}s  gas={ppm:.1f} ppm  "
                f"wind={wind_speed:.1f} m/s @ {wind_dir:.0f}°"
            )


def main(args=None):
    rclpy.init(args=args)
    node = GasLeakPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
