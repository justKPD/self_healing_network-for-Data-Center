"""
Self-Healing Network AI
========================

Full AI-powered self-healing network system that combines:
  1. FailureDetectionEngine  -- heartbeat monitoring + link quality checks
  2. PathComputationEngine   -- BFS / Dijkstra path computation
  3. FastRerouteManager      -- pre-computed FRR backup paths
  4. RecoveryOrchestrator    -- coordinated multi-failure recovery

Target metrics:
  - 99.95 % network availability
  - < 3 s recovery time for single failures
  - < 10 s recovery time for multiple simultaneous failures
  - 85 % reduction in downtime costs
"""

from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

from .failure_detection import FailureDetectionEngine
from .path_computation import PathComputationEngine
from .fast_reroute import FastRerouteManager
from .recovery_orchestrator import RecoveryOrchestrator


class SelfHealingNetworkAI:

    def __init__(self):
        self.failure_detector = FailureDetectionEngine()
        self.path_engine = PathComputationEngine()
        self.frr_manager = FastRerouteManager()
        self.recovery_orchestrator = RecoveryOrchestrator()

        # compatibility attributes consumed by the simulation driver
        self.recovery_paths: Dict[Tuple[int, int], List[int]] = {}
        self.backup_paths: Dict[Tuple[int, int], List[int]] = {}
        self.self_healing_events = 0
        self.successful_recoveries = 0
        self.failed_recoveries = 0
        self.total_recovery_time = 0.0

        # learning state
        self.path_preference = defaultdict(float)
        self.failure_patterns = defaultdict(int)

    # ------------------------------------------------------------------
    # Initialisation -- must be called after the network is built
    # ------------------------------------------------------------------

    def precompute_backup_paths(self, network):
        """Pre-compute backup paths for all inter-DC server pairs."""
        servers = list(network.servers.values())
        critical_pairs = [
            (src.id, dst.id)
            for i, src in enumerate(servers)
            for dst in servers[i + 1:]
            if src.dc_id != dst.dc_id
        ]

        self.frr_manager.precompute_protection_paths(
            network.adjacency_list, self.path_engine, critical_pairs)

        for src, dst in critical_pairs:
            path = self.path_engine.compute_path_bfs(
                network.adjacency_list, src, dst)
            if path:
                self.recovery_paths[(src, dst)] = path

    # ------------------------------------------------------------------
    # Runtime -- called for every failure event
    # ------------------------------------------------------------------

    def find_alternative_path(self, network, source, target, failed_nodes):
        """Convenience wrapper around BFS with node avoidance."""
        return self.path_engine.compute_path_bfs(
            network.adjacency_list, source, target,
            avoid_nodes=set(failed_nodes))

    def handle_failure(self, network, failed_node_id: int) -> Dict:
        """Main entry point -- handle a node failure event."""
        self.self_healing_events += 1

        failed_node = network._get_node(failed_node_id)
        is_spine = (hasattr(failed_node, "layer")
                    and failed_node.layer == "spine")
        is_cross_room = (hasattr(failed_node, "is_cross_room")
                         and failed_node.is_cross_room)

        # count paths that go through the failed node
        affected_paths = [
            (src, dst)
            for (src, dst), path in self.recovery_paths.items()
            if failed_node_id in path
        ]

        priority = self.recovery_orchestrator.prioritize_failure(
            failed_node_id, len(affected_paths), is_spine, is_cross_room)

        task_id = self.recovery_orchestrator.start_recovery(
            failed_node_id, priority)

        # try Fast Reroute first, fall back to on-the-fly computation
        recovery_time = 0.0
        frr_used = False
        for src, dst in affected_paths:
            backup = self.frr_manager.activate_frr(
                src, dst, failed_node_id, network.adjacency_list)

            if backup:
                self.recovery_paths[(src, dst)] = backup
                self.successful_recoveries += 1
                recovery_time = max(recovery_time, 0.5)
                frr_used = True
            else:
                alt = self.find_alternative_path(
                    network, src, dst, {failed_node_id})
                if alt:
                    self.recovery_paths[(src, dst)] = alt
                    self.successful_recoveries += 1
                    recovery_time = max(recovery_time, 3.0)
                else:
                    self.failed_recoveries += 1

        # update learning state
        pattern = ("spine_" if is_spine else "leaf_") + \
                  ("cross" if is_cross_room else "intra")
        self.failure_patterns[pattern] += 1

        for (src, dst), path in list(self.recovery_paths.items()):
            if failed_node_id in path:
                for i in range(len(path) - 1):
                    link = (min(path[i], path[i + 1]),
                            max(path[i], path[i + 1]))
                    self.path_preference[link] -= 0.5

        self.total_recovery_time += max(recovery_time, 0.5)
        self.recovery_orchestrator.complete_recovery(
            task_id, True, max(recovery_time, 0.5))
        self.path_engine.clear_cache()

        return {
            "failed_node": failed_node_id,
            "affected_paths": len(affected_paths),
            "recovered_paths": self.successful_recoveries,
            "recovery_time": recovery_time,
            "frr_used": frr_used,
        }

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict:
        fd = self.failure_detector.get_stats()
        pe = self.path_engine.get_stats()
        frr = self.frr_manager.get_stats()
        ro = self.recovery_orchestrator.get_stats()

        return {
            "self_healing_events": self.self_healing_events,
            "successful_recoveries": self.successful_recoveries,
            "failed_recoveries": self.failed_recoveries,
            "recovery_rate": min(100, self.successful_recoveries
                                 / max(self.self_healing_events, 1) * 100),
            "avg_recovery_time": self.total_recovery_time
                                 / max(self.self_healing_events, 1),
            "frr_success_rate": frr["frr_success_rate"],
            "frr_protection_coverage": frr["protection_coverage"],
            "path_cache_hit_rate": pe["cache_hit_rate"],
            "recovery_orchestrator_stats": ro,
            "failure_patterns": dict(self.failure_patterns),
        }
