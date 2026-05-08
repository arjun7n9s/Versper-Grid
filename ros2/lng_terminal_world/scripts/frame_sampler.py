#!/usr/bin/env python3
"""VesperGrid Frame Sampler — ROS2 node.

Subscribes to the three camera topics published by Gazebo, accumulates a
keyframe bundle every SAMPLE_INTERVAL_S seconds, then POSTs the frames as
multipart form data to POST /api/ingest/upload on the VesperGrid cloud API.

Environment variables (all optional — sensible defaults for local dev):
  VESPER_API_URL          e.g. http://165.245.143.11/api   (no trailing slash)
  SAMPLE_INTERVAL_S       seconds between bundles           default: 10
  MAX_FRAMES_PER_BUNDLE   max frames sent per POST          default: 5
  JPEG_QUALITY            0-95                              default: 75
  INCIDENT_LOCATION       free-text location tag            default: "Sector 4 — Tank B-4 Flange"
  FIELD_NOTES             operator notes injected into VLM  default: (auto)

Topics consumed (all sensor_msgs/Image, bridged from Ignition):
  /cctv_south/image_raw   — CCTV watching B-4 directly (highest priority)
  /drone_d1/image_raw     — primary drone cam orbiting the leak
  /cctv_gate/image_raw    — gate CCTV (wider context)
"""
from __future__ import annotations

import io
import logging
import os
import time
from collections import deque
from typing import Deque

import requests
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image

logger = logging.getLogger("frame_sampler")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [frame_sampler] %(levelname)s %(message)s",
)

_API_URL = os.environ.get("VESPER_API_URL", "http://165.245.143.11/api").rstrip("/")
_SAMPLE_INTERVAL = float(os.environ.get("SAMPLE_INTERVAL_S", "10"))
_MAX_FRAMES = int(os.environ.get("MAX_FRAMES_PER_BUNDLE", "5"))
_JPEG_QUALITY = int(os.environ.get("JPEG_QUALITY", "75"))
_LOCATION = os.environ.get("INCIDENT_LOCATION", "Sector 4 — Tank B-4 Flange")
_FIELD_NOTES = os.environ.get(
    "FIELD_NOTES",
    "Active LNG flange failure at Tank B-4, south cluster. "
    "Visible gas plume, worker evacuation in progress. "
    "Drone D-1 orbiting incident zone. CCTV south confirming plume spread.",
)

# Priority order for frame selection: south > drone > gate
_TOPIC_PRIORITY = [
    "/cctv_south/image_raw",
    "/drone_d1/image_raw",
    "/cctv_gate/image_raw",
]


def _ros_image_to_jpeg(msg: Image) -> bytes:
    """Convert a sensor_msgs/Image to JPEG bytes using Pillow."""
    from PIL import Image as PILImage

    encoding = msg.encoding.lower()
    w, h = msg.width, msg.height
    data = bytes(msg.data)

    if encoding in ("rgb8", "rgb"):
        pil = PILImage.frombytes("RGB", (w, h), data)
    elif encoding in ("bgr8", "bgr"):
        pil = PILImage.frombytes("RGB", (w, h), data, "raw", "BGR")
    elif encoding in ("mono8", "8uc1"):
        pil = PILImage.frombytes("L", (w, h), data).convert("RGB")
    else:
        raise ValueError(f"Unsupported encoding: {encoding}")

    buf = io.BytesIO()
    pil.save(buf, format="JPEG", quality=_JPEG_QUALITY)
    return buf.getvalue()


class FrameSampler(Node):
    def __init__(self) -> None:
        super().__init__("frame_sampler")
        self._buffers: dict[str, Deque[Image]] = {t: deque(maxlen=3) for t in _TOPIC_PRIORITY}
        self._last_post: float = 0.0
        self._job_count: int = 0

        for topic in _TOPIC_PRIORITY:
            self.create_subscription(Image, topic, self._make_cb(topic), 2)
            self.get_logger().info(f"Subscribed → {topic}")

        self.create_timer(_SAMPLE_INTERVAL / 2, self._maybe_post)
        self.get_logger().info(
            f"Frame sampler ready — posting to {_API_URL}/ingest/upload "
            f"every {_SAMPLE_INTERVAL}s, up to {_MAX_FRAMES} frames/bundle"
        )

    def _make_cb(self, topic: str):
        def cb(msg: Image):
            self._buffers[topic].append(msg)
        return cb

    def _maybe_post(self) -> None:
        now = time.monotonic()
        if now - self._last_post < _SAMPLE_INTERVAL:
            return

        # Collect one frame per topic in priority order, fill up to _MAX_FRAMES
        frames: list[tuple[str, Image]] = []
        for topic in _TOPIC_PRIORITY:
            buf = self._buffers[topic]
            if buf:
                frames.append((topic, buf[-1]))
            if len(frames) >= _MAX_FRAMES:
                break

        if not frames:
            self.get_logger().warn("No frames received yet — waiting for Gazebo cameras.")
            return

        self._last_post = now
        self._post_bundle(frames)

    def _post_bundle(self, frames: list[tuple[str, Image]]) -> None:
        files = []
        names = []
        for topic, msg in frames:
            source = topic.lstrip("/").replace("/", "_")
            ts = int(time.time())
            filename = f"{source}_{ts}.jpg"
            try:
                jpeg_bytes = _ros_image_to_jpeg(msg)
                files.append(("images", (filename, jpeg_bytes, "image/jpeg")))
                names.append(filename)
            except Exception as exc:
                self.get_logger().error(f"JPEG encode failed for {topic}: {exc}")

        if not files:
            return

        data = {
            "location": _LOCATION,
            "field_notes": _FIELD_NOTES,
            "sensor_count": str(len(frames)),
        }

        self._job_count += 1
        self.get_logger().info(
            f"[job #{self._job_count}] POSTing {len(files)} frame(s): {names}"
        )

        try:
            resp = requests.post(
                f"{_API_URL}/ingest/upload",
                files=files,
                data=data,
                timeout=30,
            )
            resp.raise_for_status()
            body = resp.json()
            job_id = body.get("job_id", "?")
            backend = body.get("backend", "?")
            self.get_logger().info(
                f"[job #{self._job_count}] Accepted → job_id={job_id} backend={backend}"
            )
            # Fire-and-forget SSE poll in background
            self.executor.create_task(self._poll_result(job_id))  # type: ignore[attr-defined]
        except Exception as exc:
            self.get_logger().error(f"[job #{self._job_count}] POST failed: {exc}")

    async def _poll_result(self, job_id: str) -> None:
        """Non-blocking await on the job result — logs final stage + confidence."""
        import asyncio
        import httpx

        url = f"{_API_URL}/ingest/{job_id}/await"
        await asyncio.sleep(2)
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                r = await client.post(url, params={"timeout_seconds": 110})
                r.raise_for_status()
                snap = r.json()
            status = snap.get("status")
            backend = snap.get("backend")
            result = snap.get("result") or {}
            n_evidence = len(result.get("evidence", []))
            n_hazards = len([
                e for e in result.get("evidence", [])
                if e.get("type") == "Hazard"
            ])
            self.get_logger().info(
                f"[job {job_id}] DONE — status={status} backend={backend} "
                f"evidence={n_evidence} hazards={n_hazards}"
            )
        except Exception as exc:
            self.get_logger().warn(f"[job {job_id}] poll failed: {exc}")


def main(args=None):
    rclpy.init(args=args)
    node = FrameSampler()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
