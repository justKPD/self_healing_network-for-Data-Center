"""
Failure Detection Engine
========================

Monitors network health via heartbeat messages and link quality checks.
Detects failures within configurable timeout windows.

Detection methods:
  1. Heartbeat timeout -- missing N consecutive heartbeats triggers alert
  2. Link quality degradation -- BER exceeding threshold
  3. Path latency anomaly -- sudden latency spike relative to baseline
"""

import numpy as np
from collections import defaultdict
from typing import List, Dict, Optional


class FailureDetectionEngine:

    def __init__(self, heartbeat_interval_ms=1000, missed_heartbeats_threshold=3,
                 ber_threshold=1e-9, latency_spike_factor=3.0):
        self.heartbeat_interval = heartbeat_interval_ms
        self.missed_threshold = missed_heartbeats_threshold
        self.ber_threshold = ber_threshold
        self.latency_spike_factor = latency_spike_factor

        self.missing_heartbeats = defaultdict(int)
        self.last_heartbeat = {}
        self.link_ber = defaultdict(float)
        self.baseline_latency = defaultdict(float)

        self.detections = []
        self.detection_times = []

    def process_heartbeat(self, node_id: int, timestamp: float):
        """Register a received heartbeat from a monitored node."""
        self.last_heartbeat[node_id] = timestamp
        self.missing_heartbeats[node_id] = 0

    def check_timeouts(self, current_time: float) -> List[int]:
        """Return list of node IDs that have missed too many heartbeats."""
        failed = []

        for node_id, last_time in list(self.last_heartbeat.items()):
            elapsed = current_time - last_time
            if elapsed > self.heartbeat_interval * self.missed_threshold:
                failed.append(node_id)

        for node_id in list(self.missing_heartbeats.keys()):
            self.missing_heartbeats[node_id] += 1
            if self.missing_heartbeats[node_id] >= self.missed_threshold:
                if node_id not in failed:
                    failed.append(node_id)

        return failed

    def check_link_quality(self, from_node: int, to_node: int,
                           ber: float, latency: float) -> Optional[Dict]:
        """Check whether a link's quality indicates impending failure."""
        link_key = (from_node, to_node)
        issues = []

        if ber > self.ber_threshold:
            issues.append("high_ber")

        if link_key in self.baseline_latency:
            baseline = self.baseline_latency[link_key]
            if latency > baseline * self.latency_spike_factor:
                issues.append("latency_spike")

        # update baseline with EMA
        if link_key not in self.baseline_latency:
            self.baseline_latency[link_key] = latency
        else:
            self.baseline_latency[link_key] = (
                0.9 * self.baseline_latency[link_key] + 0.1 * latency
            )
        self.link_ber[link_key] = ber

        if issues:
            return {
                "link": link_key,
                "issues": issues,
                "ber": ber,
                "latency": latency,
                "baseline_latency": self.baseline_latency[link_key],
            }
        return None

    def get_stats(self) -> Dict:
        return {
            "total_detections": len(self.detections),
            "avg_detection_time_ms": (
                np.mean(self.detection_times) if self.detection_times else 0
            ),
            "monitored_nodes": len(self.last_heartbeat),
            "monitored_links": len(self.link_ber),
        }
