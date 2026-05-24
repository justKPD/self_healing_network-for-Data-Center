# Architecture

## Component Overview

```
                    ┌─────────────────────────┐
                    │   SelfHealingNetworkAI   │
                    │      (main interface)    │
                    └─────────┬───────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
   ┌──────▼──────┐   ┌───────▼───────┐   ┌──────▼──────┐
   │  Failure    │   │  Path         │   │  Recovery   │
   │  Detection  │   │  Computation  │   │  Orchestr.  │
   │  Engine     │   │  Engine       │   │             │
   └─────────────┘   └───────┬───────┘   └─────────────┘
                              │
                     ┌────────▼────────┐
                     │  Fast Reroute   │
                     │  Manager (FRR)  │
                     └─────────────────┘
```

## Failure Detection Engine

Monitors every active node through periodic heartbeat messages.
A node is declared failed after N consecutive missed heartbeats
(default: 3 × 1 s interval = 3 s).  Additionally monitors link
quality via BER thresholds and latency-spike detection against an
exponentially-weighted moving-average baseline.

## Path Computation Engine

Two algorithms are provided:

| Algorithm | Use case | Complexity |
|-----------|----------|------------|
| BFS       | Shortest hop-count path, fast | O(V + E) |
| Dijkstra  | Weighted shortest path (latency, load) | O((V+E) log V) |

Both support constraint parameters: avoid-nodes, avoid-links, max-hops.
A k-shortest-paths mode computes up to N link-diverse paths.

## Fast Reroute Manager

Pre-computes backup paths for every critical source-destination pair.
Two protection levels:

- **Node protection**: backup avoids a specific intermediate node
- **Link protection**: backup avoids a specific link

On failure, the FRR manager tries to activate a pre-computed backup
(sub-second switchover).  If no backup is valid, it falls back to
on-the-fly path computation.

## Recovery Orchestrator

Coordinates recovery when multiple failures occur simultaneously.
Failures are prioritised by: spine > leaf, cross-room > intra-room,
and number of affected paths.  The orchestrator limits concurrent
recovery tasks and learns which strategies work best over time.

## Data Flow

1. **Startup**: `precompute_backup_paths()` computes FRR paths for
   all inter-DC server pairs.
2. **Failure event**: `handle_failure()` is called with the failed
   node ID.
3. **Priority**: Recovery orchestrator assigns a priority score.
4. **FRR attempt**: For each affected path, try pre-computed backup.
5. **Fallback**: If FRR fails, run BFS with node avoidance.
6. **Update**: Path preferences are adjusted (demote paths through
   the failed node).  Path cache is cleared.
