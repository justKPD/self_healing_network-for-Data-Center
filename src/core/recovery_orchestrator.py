"""
Recovery Orchestrator
======================

Coordinates multi-failure recovery across the network.
Handles single failures (fast path), multiple simultaneous failures
(coordinated recovery), and learns which recovery strategies work best.
"""

import time as _time
from collections import defaultdict
from typing import Dict


class RecoveryOrchestrator:

    def __init__(self, max_concurrent_recoveries=5):
        self.max_concurrent = max_concurrent_recoveries
        self.recovery_queue = []
        self.active_recoveries = {}
        self.completed_recoveries = 0
        self.failed_recoveries = 0
        self.total_recovery_time = 0.0
        self.strategy_success = defaultdict(lambda: {"attempts": 0, "successes": 0})

    def prioritize_failure(self, failed_node_id: int, affected_paths: int,
                           is_spine: bool, is_cross_room: bool) -> float:
        """Compute priority score -- higher value means more urgent."""
        priority = 0.0
        if is_spine:
            priority += 50.0
        if is_cross_room:
            priority += 30.0
        priority += min(affected_paths * 2.0, 20.0)
        return priority

    def start_recovery(self, failed_node_id: int, priority: float,
                       recovery_strategy: str = "auto") -> str:
        task_id = f"rec_{failed_node_id}_{len(self.active_recoveries)}"
        if len(self.active_recoveries) >= self.max_concurrent:
            self.recovery_queue.append(
                (priority, task_id, failed_node_id, recovery_strategy))
            return task_id

        self.active_recoveries[task_id] = {
            "node_id": failed_node_id,
            "strategy": recovery_strategy,
            "start_time": _time.time(),
            "priority": priority,
        }
        return task_id

    def complete_recovery(self, task_id: str, success: bool,
                          recovery_time: float):
        if task_id in self.active_recoveries:
            strategy = self.active_recoveries[task_id]["strategy"]
            self.strategy_success[strategy]["attempts"] += 1
            if success:
                self.strategy_success[strategy]["successes"] += 1
                self.completed_recoveries += 1
            else:
                self.failed_recoveries += 1
            self.total_recovery_time += recovery_time
            del self.active_recoveries[task_id]

            # pick next queued recovery
            if self.recovery_queue:
                self.recovery_queue.sort(key=lambda x: -x[0])
                pri, tid, nid, strat = self.recovery_queue.pop(0)
                self.start_recovery(nid, pri, strat)

    def get_best_strategy(self) -> str:
        best, best_rate = "auto", 0.0
        for strategy, stats in self.strategy_success.items():
            if stats["attempts"] > 0:
                rate = stats["successes"] / stats["attempts"]
                if rate > best_rate:
                    best_rate = rate
                    best = strategy
        return best

    def get_stats(self) -> Dict:
        return {
            "completed_recoveries": self.completed_recoveries,
            "failed_recoveries": self.failed_recoveries,
            "avg_recovery_time": self.total_recovery_time / max(self.completed_recoveries, 1),
            "active_recoveries": len(self.active_recoveries),
            "queued_recoveries": len(self.recovery_queue),
            "best_strategy": self.get_best_strategy(),
        }
