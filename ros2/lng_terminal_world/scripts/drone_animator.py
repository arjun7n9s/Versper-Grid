#!/usr/bin/env python3
"""
Drone Animator — moves D-1, D-2, D-3 in the lng_terminal world via Ignition's
/world/<world>/set_pose service.

D-1 (primary, has camera): hovers near tank B-4, gentle bob + beacon "blink"
    via tiny vertical jitter so the LED reads as pulsing.
D-2 (small, parked on pad): cycles take-off → patrol → land.
D-3 (medium, Sector 2): random walk over its sector.

Strategy is reusable for any future pose publisher: just call ign-service in a
loop with computed poses.
"""
import math
import random
import subprocess
import time
import threading

import rclpy
from rclpy.node import Node

WORLD = "lng_terminal"
SERVICE = f"/world/{WORLD}/set_pose"


def set_pose(name, x, y, z, yaw=0.0):
    """Call ign service to teleport a model to a new pose."""
    qz = math.sin(yaw / 2.0)
    qw = math.cos(yaw / 2.0)
    req = (
        f'name: "{name}", '
        f'position: {{x: {x:.3f}, y: {y:.3f}, z: {z:.3f}}}, '
        f'orientation: {{x: 0, y: 0, z: {qz:.4f}, w: {qw:.4f}}}'
    )
    try:
        subprocess.run(
            [
                "ign", "service",
                "-s", SERVICE,
                "--reqtype", "ignition.msgs.Pose",
                "--reptype", "ignition.msgs.Boolean",
                "--timeout", "200",
                "--req", req,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=1.0,
        )
    except Exception:
        pass  # service may not be ready yet


class DroneAnimator(Node):
    def __init__(self):
        super().__init__("drone_animator")
        self.t0 = time.time()
        # D-3 random walk state
        self.d3_x = 440.0
        self.d3_y = 30.0
        self.d3_z = 25.0
        self.d3_yaw = 1.2
        self.d3_target = self._new_d3_target()
        # D-2 mission state machine: takeoff → patrol → land → idle
        self.d2_phase = "takeoff"
        self.d2_phase_start = time.time()
        # 10 Hz update
        self.timer = self.create_timer(0.1, self.tick)
        self.get_logger().info("DroneAnimator started — D-1 hover/blink, D-2 patrol cycle, D-3 random walk")

    # ── D-3 helpers ──
    def _new_d3_target(self):
        return (
            440.0 + random.uniform(-80, 80),
            30.0 + random.uniform(-80, 80),
            22.0 + random.uniform(-4, 8),
        )

    def tick(self):
        t = time.time() - self.t0

        # ── D-1: hover near B-4, subtle bob; beacon "blink" via micro-jitter
        # The beacon is rendered as a bright red sphere on top of the drone; we
        # toggle the model's z-position by ±0.03m at ~2 Hz. The visual jitter
        # on the bright LED reads convincingly as pulsing/strobing.
        blink = 0.05 if int(t * 2) % 2 == 0 else -0.05
        bob = 0.25 * math.sin(t * 1.2)
        d1_x = 72.0 + 0.4 * math.sin(t * 0.3)
        d1_y = -50.0 + 0.4 * math.cos(t * 0.3)
        d1_z = 18.0 + bob + blink
        d1_yaw = -2.4 + 0.05 * math.sin(t * 0.5)
        set_pose("drone_d1", d1_x, d1_y, d1_z, d1_yaw)

        # ── D-2: take-off → patrol → land → idle (then loop)
        phase_t = time.time() - self.d2_phase_start
        if self.d2_phase == "takeoff":
            # rise from pad (0,10,0.18) to 12m over 4s
            z = 0.18 + (12.0 - 0.18) * min(1.0, phase_t / 4.0)
            set_pose("drone_d2", 0.0, 10.0, z, 0.4)
            if phase_t > 4.0:
                self.d2_phase = "patrol"
                self.d2_phase_start = time.time()
        elif self.d2_phase == "patrol":
            # circle around pad at radius ~30m, altitude 12m, for 16s
            ang = phase_t * 0.4
            x = 0.0 + 30.0 * math.cos(ang)
            y = 10.0 + 30.0 * math.sin(ang)
            z = 12.0 + 1.5 * math.sin(phase_t * 0.8)
            yaw = ang + math.pi / 2
            set_pose("drone_d2", x, y, z, yaw)
            if phase_t > 16.0:
                self.d2_phase = "land"
                self.d2_phase_start = time.time()
        elif self.d2_phase == "land":
            # descend back to pad over 4s
            z = 12.0 - (12.0 - 0.18) * min(1.0, phase_t / 4.0)
            set_pose("drone_d2", 0.0, 10.0, z, 0.4)
            if phase_t > 4.0:
                self.d2_phase = "idle"
                self.d2_phase_start = time.time()
        elif self.d2_phase == "idle":
            # parked for 3s, then take off again
            set_pose("drone_d2", 0.0, 10.0, 0.18, 0.4)
            if phase_t > 3.0:
                self.d2_phase = "takeoff"
                self.d2_phase_start = time.time()

        # ── D-3: smooth random walk toward changing targets in Sector 2
        tx, ty, tz = self.d3_target
        dx = tx - self.d3_x
        dy = ty - self.d3_y
        dz = tz - self.d3_z
        dist = math.sqrt(dx * dx + dy * dy + dz * dz)
        if dist < 3.0:
            self.d3_target = self._new_d3_target()
        else:
            speed = 4.0  # m/s
            step = speed * 0.1  # per 0.1s tick
            f = step / max(dist, 0.01)
            self.d3_x += dx * f
            self.d3_y += dy * f
            self.d3_z += dz * f
            self.d3_yaw = math.atan2(dy, dx)
        set_pose("drone_d3", self.d3_x, self.d3_y, self.d3_z, self.d3_yaw)


def main():
    rclpy.init()
    node = DroneAnimator()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
