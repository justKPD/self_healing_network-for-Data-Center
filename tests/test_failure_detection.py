"""Unit tests for FailureDetectionEngine."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.core.failure_detection import FailureDetectionEngine


def test_heartbeat_processing():
    fd = FailureDetectionEngine(heartbeat_interval_ms=1000,
                                missed_heartbeats_threshold=3)
    fd.process_heartbeat(1, 0.0)
    fd.process_heartbeat(2, 0.0)
    assert 1 in fd.last_heartbeat
    assert 2 in fd.last_heartbeat
    assert fd.missing_heartbeats[1] == 0


def test_timeout_detection():
    fd = FailureDetectionEngine(heartbeat_interval_ms=1000,
                                missed_heartbeats_threshold=3)
    fd.process_heartbeat(1, 0.0)
    # node 1 missed heartbeats for 4 seconds
    failed = fd.check_timeouts(4000.0)
    assert 1 in failed


def test_link_quality_high_ber():
    fd = FailureDetectionEngine(ber_threshold=1e-9)
    result = fd.check_link_quality(10, 20, ber=1e-6, latency=5.0)
    assert result is not None
    assert "high_ber" in result["issues"]


def test_link_quality_latency_spike():
    fd = FailureDetectionEngine(latency_spike_factor=3.0)
    # establish baseline
    fd.check_link_quality(10, 20, ber=0, latency=5.0)
    fd.check_link_quality(10, 20, ber=0, latency=5.0)
    # spike
    result = fd.check_link_quality(10, 20, ber=0, latency=20.0)
    assert result is not None
    assert "latency_spike" in result["issues"]


def test_normal_link_returns_none():
    fd = FailureDetectionEngine(ber_threshold=1e-9)
    result = fd.check_link_quality(1, 2, ber=1e-12, latency=5.0)
    assert result is None


if __name__ == "__main__":
    test_heartbeat_processing()
    test_timeout_detection()
    test_link_quality_high_ber()
    test_link_quality_latency_spike()
    test_normal_link_returns_none()
    print("All FailureDetection tests passed.")
