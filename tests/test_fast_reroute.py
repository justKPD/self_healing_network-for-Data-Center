"""Unit tests for FastRerouteManager."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from collections import defaultdict
from src.core.path_computation import PathComputationEngine
from src.core.fast_reroute import FastRerouteManager


class StubCable:
    def __init__(self, fid, tid):
        self.from_node = fid
        self.to_node = tid
        self.is_active = True
        self.length = 10


def _build_mesh():
    adj = defaultdict(list)
    links = [(1, 2), (2, 3), (3, 4), (4, 5), (5, 6),
             (1, 3), (2, 5), (3, 6)]
    for a, b in links:
        c = StubCable(a, b)
        adj[a].append((b, c))
        adj[b].append((a, c))
    return adj


def test_precompute():
    adj = _build_mesh()
    engine = PathComputationEngine()
    frr = FastRerouteManager()
    frr.precompute_protection_paths(adj, engine, [(1, 6)])
    assert len(frr.primary_paths) >= 1
    assert len(frr.backup_paths) >= 1


def test_activate_success():
    adj = _build_mesh()
    engine = PathComputationEngine()
    frr = FastRerouteManager()
    frr.precompute_protection_paths(adj, engine, [(1, 6)])
    result = frr.activate_frr(1, 6, 3, adj)
    assert result is not None
    stats = frr.get_stats()
    assert stats["frr_successes"] >= 1


def test_activate_failure():
    adj = defaultdict(list)
    c = StubCable(1, 2)
    adj[1].append((2, c))
    adj[2].append((1, c))
    engine = PathComputationEngine()
    frr = FastRerouteManager()
    # no precomputed paths for (1, 99)
    result = frr.activate_frr(1, 99, 5, adj)
    assert result is None


if __name__ == "__main__":
    test_precompute()
    test_activate_success()
    test_activate_failure()
    print("All FastReroute tests passed.")
