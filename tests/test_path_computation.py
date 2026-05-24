"""Unit tests for PathComputationEngine."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from collections import defaultdict
from src.core.path_computation import PathComputationEngine


class StubCable:
    def __init__(self, fid, tid, length=10):
        self.from_node = fid
        self.to_node = tid
        self.is_active = True
        self.length = length


def _build_mesh():
    """Small 6-node mesh for testing."""
    adj = defaultdict(list)
    links = [(1, 2, 10), (2, 3, 15), (3, 4, 10), (4, 5, 12),
             (5, 6, 8), (1, 3, 25), (2, 5, 20)]
    for a, b, l in links:
        c = StubCable(a, b, l)
        adj[a].append((b, c))
        adj[b].append((a, c))
    return adj


def test_bfs_finds_path():
    adj = _build_mesh()
    engine = PathComputationEngine()
    path = engine.compute_path_bfs(adj, 1, 6)
    assert path is not None
    assert path[0] == 1
    assert path[-1] == 6


def test_bfs_no_path():
    adj = defaultdict(list)
    c = StubCable(1, 2)
    adj[1].append((2, c))
    adj[2].append((1, c))
    engine = PathComputationEngine()
    path = engine.compute_path_bfs(adj, 1, 99)
    assert path is None


def test_bfs_avoid_node():
    adj = _build_mesh()
    engine = PathComputationEngine()
    path_normal = engine.compute_path_bfs(adj, 1, 6)
    path_avoid = engine.compute_path_bfs(adj, 1, 6, avoid_nodes={2})
    assert path_avoid is not None
    assert 2 not in path_avoid


def test_dijkstra_finds_path():
    adj = _build_mesh()
    engine = PathComputationEngine()
    path = engine.compute_path_dijkstra(adj, 1, 6)
    assert path is not None
    assert path[0] == 1
    assert path[-1] == 6


def test_multiple_paths():
    adj = _build_mesh()
    engine = PathComputationEngine()
    paths = engine.compute_multiple_paths(adj, 1, 6, n_paths=3)
    assert len(paths) >= 1
    for p in paths:
        assert p[0] == 1
        assert p[-1] == 6


def test_cache_hits():
    adj = _build_mesh()
    engine = PathComputationEngine()
    engine.compute_path_bfs(adj, 1, 6)
    engine.compute_path_bfs(adj, 1, 6)
    stats = engine.get_stats()
    assert stats["cache_hits"] >= 1


if __name__ == "__main__":
    test_bfs_finds_path()
    test_bfs_no_path()
    test_bfs_avoid_node()
    test_dijkstra_finds_path()
    test_multiple_paths()
    test_cache_hits()
    print("All PathComputation tests passed.")
