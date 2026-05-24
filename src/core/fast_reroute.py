"""
Fast Reroute (FRR) Manager
============================

Pre-computes backup paths for Fast Reroute protection.
When a link or node fails, traffic is immediately switched to the
pre-computed backup path without waiting for re-convergence.

Protection schemes:
  - Link protection:  backup avoids a specific link
  - Node protection:  backup avoids a specific intermediate node
"""

from collections import defaultdict
from typing import List, Dict, Tuple, Optional

from .path_computation import PathComputationEngine


class FastRerouteManager:

    def __init__(self):
        self.primary_paths: Dict[Tuple[int, int], List[int]] = {}
        self.backup_paths: Dict[Tuple[int, int, ...], List[int]] = {}
        self.frr_activations = 0
        self.frr_successes = 0
        self.frr_failures = 0
        self.protection_coverage = 0.0

    def precompute_protection_paths(self, adjacency_list: Dict,
                                     path_engine: PathComputationEngine,
                                     critical_pairs: List[Tuple[int, int]]):
        """Pre-compute primary and backup paths for all critical src-dst pairs."""
        total_protected = 0
        total_critical = len(critical_pairs)

        for src, dst in critical_pairs:
            primary = path_engine.compute_path_bfs(adjacency_list, src, dst)
            if primary is None:
                continue
            self.primary_paths[(src, dst)] = primary

            # node-protection backups (skip source and destination)
            for node in primary[1:-1]:
                backup = path_engine.compute_path_bfs(
                    adjacency_list, src, dst, avoid_nodes={node})
                if backup:
                    self.backup_paths[(src, dst, node)] = backup
                    total_protected += 1

            # link-protection backups
            for i in range(len(primary) - 1):
                link = (min(primary[i], primary[i + 1]),
                        max(primary[i], primary[i + 1]))
                backup = path_engine.compute_path_bfs(
                    adjacency_list, src, dst, avoid_links={link})
                if backup:
                    self.backup_paths[(src, dst, link[0], link[1])] = backup
                    total_protected += 1

        self.protection_coverage = total_protected / max(total_critical * 5, 1) * 100

    def activate_frr(self, src: int, dst: int, failed_entity,
                     adjacency_list: Dict) -> Optional[List[int]]:
        """Try to activate a pre-computed FRR backup for the failed entity."""
        self.frr_activations += 1

        # look up pre-computed backup
        if isinstance(failed_entity, tuple):
            key = (src, dst, failed_entity[0], failed_entity[1])
        else:
            key = (src, dst, failed_entity)

        if key in self.backup_paths:
            backup = self.backup_paths[key]
            if self._verify_path(backup, adjacency_list):
                self.frr_successes += 1
                return backup

        self.frr_failures += 1
        return None

    def _verify_path(self, path: List[int], adjacency_list: Dict) -> bool:
        """Check that every link along the path is still active."""
        for i in range(len(path) - 1):
            if path[i] not in adjacency_list:
                return False
            found = False
            for neighbor, cable in adjacency_list[path[i]]:
                if neighbor == path[i + 1] and cable.is_active:
                    found = True
                    break
            if not found:
                return False
        return True

    def get_stats(self) -> Dict:
        return {
            "frr_activations": self.frr_activations,
            "frr_successes": self.frr_successes,
            "frr_failures": self.frr_failures,
            "frr_success_rate": self.frr_successes / max(self.frr_activations, 1) * 100,
            "protection_coverage": self.protection_coverage,
            "protected_paths": len(self.primary_paths),
            "backup_paths_computed": len(self.backup_paths),
        }
