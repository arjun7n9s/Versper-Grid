"""VesperGrid Evidence Bridge — ROS2 node.

Subscribes to Gazebo-published topics, batches a burst of frames when an
incident trigger is detected (or manually via ROS2 service call), saves
JPEGs to disk, and POSTs them to the VesperGrid API /api/ingest/upload.

Subscribed topics:
  /drone_cam/image_raw        sensor_msgs/Image
  /cctv_gate/image_raw        sensor_msgs/Image
  /gas_sensor_0/reading       std_msgs/Float32   (ppm concentration)
  /wind/state                 std_msgs/String    (JSON: speed_mps, direction_deg)

Service:
  /vespergrid/trigger_ingest  std_srvs/Trigger   (manual trigger)

Parameters (set via ROS2 param or env):
  api_url         default: http://localhost:8742
  location        default: LNG Terminal Alpha, Chennai Corridor
  auto_trigger    default: true  (trigger on gas reading > threshold_ppm)
  threshold_ppm   default: 15.0
  frames_per_cam  default: 3     (how many frames to include per camera)
"""
from __future__ import annotations

import io
import json
import os
import time
from collections import deque
from pathlib import Path

import requests
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import Float32, String
from std_srvs.srv import Trigger


class EvidenceBridge(Node):
    def __init__(self):
        super().__init__("evidence_bridge")

        self.declare_parameter("api_url", os.environ.get("VESPER_API_URL", "http://localhost:8742"))
        self.declare_parameter("location", "LNG Terminal Alpha, Chennai Corridor")
        self.declare_parameter("auto_trigger", True)
        self.declare_parameter("threshold_ppm", 15.0)
        self.declare_parameter("frames_per_cam", 3)

        self._api_url = self.get_parameter("api_url").value
        self._location = self.get_parameter("location").value
        self._auto_trigger = self.get_parameter("auto_trigger").value
        self._threshold_ppm = self.get_parameter("threshold_ppm").value
        self._frames_per_cam = int(self.get_parameter("frames_per_cam").value)

        self._bridge = CvBridge()
        self._drone_buf: deque = deque(maxlen=10)
        self._cctv_buf: deque = deque(maxlen=10)
        self._gas_readings: deque = deque(maxlen=30)
        self._wind_state: dict = {}
        self._last_trigger_ts: float = 0.0
        self._cooldown_s: float = 30.0
        self._ingest_count: int = 0

        self.create_subscription(Image, "/drone_cam/image_raw", self._drone_cb, 5)
        self.create_subscription(Image, "/cctv_gate/image_raw", self._cctv_cb, 5)
        self.create_subscription(Float32, "/gas_sensor_0/reading", self._gas_cb, 10)
        self.create_subscription(String, "/wind/state", self._wind_cb, 10)

        self.create_service(Trigger, "/vespergrid/trigger_ingest", self._trigger_srv)

        self.get_logger().info(
            f"EvidenceBridge ready — API={self._api_url}, "
            f"auto_trigger={self._auto_trigger}, threshold={self._threshold_ppm} ppm"
        )

    def _drone_cb(self, msg: Image) -> None:
        try:
            cv_img = self._bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
            self._drone_buf.append((time.time(), cv_img))
        except Exception as e:
            self.get_logger().warn(f"drone frame decode error: {e}")

    def _cctv_cb(self, msg: Image) -> None:
        try:
            cv_img = self._bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
            self._cctv_buf.append((time.time(), cv_img))
        except Exception as e:
            self.get_logger().warn(f"cctv frame decode error: {e}")

    def _gas_cb(self, msg: Float32) -> None:
        reading = msg.data
        self._gas_readings.append((time.time(), reading))
        if self._auto_trigger and reading > self._threshold_ppm:
            now = time.time()
            if now - self._last_trigger_ts > self._cooldown_s:
                self.get_logger().warn(
                    f"Gas reading {reading:.1f} ppm exceeds threshold "
                    f"{self._threshold_ppm} — auto-triggering ingest"
                )
                self._do_ingest(
                    field_notes=f"Auto-trigger: gas sensor reading {reading:.1f} ppm at t={now:.0f}"
                )

    def _wind_cb(self, msg: String) -> None:
        try:
            self._wind_state = json.loads(msg.data)
        except Exception:
            pass

    def _trigger_srv(self, request, response):
        self.get_logger().info("Manual trigger received via service call.")
        success = self._do_ingest(field_notes="Manual trigger via /vespergrid/trigger_ingest")
        response.success = success
        response.message = "Ingest dispatched" if success else "Ingest failed — check logs"
        return response

    def _do_ingest(self, field_notes: str = "") -> bool:
        self._last_trigger_ts = time.time()
        self._ingest_count += 1

        import cv2
        files = []
        saved = []

        def encode_frames(buf, prefix: str):
            frames = list(buf)[-self._frames_per_cam:]
            for i, (ts, img) in enumerate(frames):
                ok, buf_enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
                if ok:
                    fname = f"{prefix}_frame_{i:02d}.jpg"
                    files.append(("images", (fname, io.BytesIO(buf_enc.tobytes()), "image/jpeg")))
                    saved.append(fname)

        encode_frames(self._drone_buf, "drone_cam")
        encode_frames(self._cctv_buf, "cctv_gate")

        if not files:
            self.get_logger().warn("No frames buffered — skipping ingest")
            return False

        gas_recent = [r for _, r in list(self._gas_readings)[-5:]]
        gas_avg = sum(gas_recent) / len(gas_recent) if gas_recent else 0.0
        wind_note = (
            f"Wind: {self._wind_state.get('speed_mps', '?')} m/s "
            f"@ {self._wind_state.get('direction_deg', '?')}°"
            if self._wind_state else "Wind data unavailable"
        )
        full_notes = (
            f"{field_notes}\n"
            f"Gas sensor avg (last 5s): {gas_avg:.2f} ppm\n"
            f"{wind_note}\n"
            f"Ingest #{self._ingest_count}"
        ).strip()

        data = {
            "location": self._location,
            "field_notes": full_notes,
            "sensor_count": str(len(self._gas_readings)),
        }

        url = f"{self._api_url}/api/ingest/upload"
        try:
            resp = requests.post(url, data=data, files=files, timeout=30)
            resp.raise_for_status()
            job = resp.json()
            self.get_logger().info(
                f"Ingest job dispatched: job_id={job.get('job_id')}, "
                f"images={job.get('image_count')}, backend={job.get('backend')}"
            )
            return True
        except Exception as exc:
            self.get_logger().error(f"Ingest POST failed: {exc}")
            return False


def main(args=None):
    rclpy.init(args=args)
    node = EvidenceBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
