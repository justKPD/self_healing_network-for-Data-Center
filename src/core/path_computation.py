"""
Path Computation Engine
========================

Computes optimal paths through the network topology.
Supports BFS (shortest hop count) and Dijkstra (weighted) algorithms
with constraint options: avoid nodes/links, max hops, custom weights.
"""

import heapq
from collections import defaultdict, deque
from typing import List, Dict, Tuple, Optional, Set


class PathComputationEngine:

    def __init__(self):
        self.path_cache = {}
        self.cache_hits = 0
        self.cache_misses = 0

    # ------------------------------------------------------------------
    # BFS shortest path (unweighted, minimum hops)
    # ------------------------------------------------------------------

    def compute_path_bfs(self, adjacency_list: Dict, source: int, target: int,
                         avoid_nodes: Set[int] = None,
                         avoid_links: Set[Tuple[int, int]] = None,
                         max_hops: int = 15) -> Optional[List[int]]:
        if avoid_nodes is None:
            avoid_nodes = set()
        if avoid_links is None:
            avoid_links = set()

        cache_key = (source, target,
                     tuple(sorted(avoid_nodes)),
                     tuple(sorted(avoid_links)))
        if cache_key in self.path_cache:
            self.cache_hits += 1
            return self.path_cache[cache_key]

        self.cache_misses += 1
        visited = avoid_nodes.copy()
        queue = deque([(source, [source])])

        while queue:
            current, path = queue.popleft()
            if current == target:
                if len(path) <= max_hops:
                    self.path_cache[cache_key] = path
                    return path
                continue
            if current in visited:
                continue
            visited.add(current)

            if current in adjacency_list:
                for neighbor_id, cable in adjacency_list[current]:
                    if neighbor_id in visited:
                        continue
                    if not cable.is_active:
                        continue
                    link = (min(current, neighbor_id),
                            max(current, neighbor_id))
                    if link in avoid_links:
                        continue
                    queue.append((neighbor_id, path + [neighbor_id]))

        return None

    # ------------------------------------------------------------------
    # Dijkstra weighted shortest path
    # ------------------------------------------------------------------

    def compute_path_dijkstra(self, adjacency_list: Dict, source: int,
                               target: int, avoid_nodes: Set[int] = None,
                               weight_func=None, max_hops: int = 15
                               ) -> Optional[List[int]]:
        if avoid_nodes is None:
            avoid_nodes = set()

        distances = {source: 0}
        previous = {}
        visited = set(avoid_nodes)
        heap = [(0, source)]

        while heap:
            dist, current = heapq.heappop(heap)
            if current in visited:
                continue
            visited.add(current)

            if current == target:
                path = []
                node = target
                while node in previous:
                    path.append(node)
                    node = previous[node]
                path.append(source)
                path.reverse()
                return path if len(path) <= max_hops else None

            if current in adjacency_list:
                for neighbor_id, cable in adjacency_list[current]:
                    if neighbor_id in visited or not cable.is_active:
                        continue
                    weight = (weight_func(cable, current, neighbor_id)
                              if weight_func else cable.length * 0.01)
                    new_dist = dist + weight
                    if neighbor_id not in distances or new_dist < distances[neighbor_id]:
                        distances[neighbor_id] = new_dist
                        previous[neighbor_id] = current
                        heapq.heappush(heap, (new_dist, neighbor_id))

        return None

    # ------------------------------------------------------------------
    # K-shortest diverse paths
    # ------------------------------------------------------------------

    def compute_multiple_paths(self, adjacency_list: Dict, source: int,
                                target: int, n_paths: int = 3
                                ) -> List[List[int]]:
        paths = []
        path1 = self.compute_path_bfs(adjacency_list, source, target)
        if path1:
            paths.append(path1)

        used_links = set()
        for prev_path in paths:
            for i in range(len(prev_path) - 1):
                used_links.add((min(prev_path[i], prev_path[i + 1]),
                                max(prev_path[i], prev_path[i + 1])))

        while len(paths) < n_paths:
            new_path = self.compute_path_bfs(
                adjacency_list, source, target,
                avoid_links=used_links.copy())
            if new_path is None:
                break
            paths.append(new_path)
            for i in range(len(new_path) - 1):
                used_links.add((min(new_path[i], new_path[i + 1]),
                                max(new_path[i], new_path[i + 1])))

        return paths

    def clear_cache(self):
        self.path_cache.clear()

    def get_stats(self) -> Dict:
        total = self.cache_hits + self.cache_misses
        return {
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_size": len(self.path_cache),
            "cache_hit_rate": self.cache_hits / max(total, 1) * 100,
        }
