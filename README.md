# Self-Healing Network AI
<img width="1485" height="887" alt="image" src="https://github.com/user-attachments/assets/8e637c35-0e29-403f-9536-7ab71c14af8f" />

Autonomous network recovery system for data center spine-leaf topologies.
Detects failures in real time and reroutes traffic through pre-computed
backup paths with sub-second failover.

## Problem

In a multi-room data center (e.g. THD Deggendorf Lehrrechenzentrum with
3 rooms, 96 servers, 9 switches), a single spine switch failure takes
down all inter-room traffic for that room.  Manual recovery typically
takes 15-60 minutes.  Over a 365-day period this adds up to significant
downtime and cost.

## Solution

Four cooperating components:

| Component | Role | Recovery time |
|-----------|------|---------------|
| **Failure Detection Engine** | Heartbeat monitoring + BER/latency anomaly checks | < 3 s |
| **Path Computation Engine** | BFS / Dijkstra with constraint satisfaction | < 1 s |
| **Fast Reroute (FRR) Manager** | Pre-computed backup paths (node + link protection) | < 0.5 s |
| **Recovery Orchestrator** | Priority-based multi-failure coordination | adaptive |

### How it works

```
  Normal operation          Failure detected           Traffic rerouted
  ──────────────────       ──────────────────        ──────────────────
  Server A ──► Spine       Server A ──╳ Spine        Server A ──► Leaf ──►
       │                         │                         │          Spine2
       ▼                         ╳                         ▼
  Server B                  (link broken)            Server B
```

When a failure is detected:

1. **FRR activation** (sub-second): pre-computed backup path is loaded
2. **BFS recomputation** (~3 s): if no valid backup exists, a new path
   is computed avoiding the failed node
3. **Path preference update**: failed paths are demoted so future
   routing avoids them

## Project structure

```
self_healing_network/
├── README.md
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── config.py                  # THD Deggendorf specifications
│   ├── simulation.py              # Standalone 365-day simulation driver
│   ├── core/
│   │   ├── __init__.py
│   │   ├── failure_detection.py   # Heartbeat + BER + latency monitoring
│   │   ├── path_computation.py    # BFS / Dijkstra / k-shortest-paths
│   │   ├── fast_reroute.py        # Pre-computed FRR backup paths
│   │   ├── recovery_orchestrator.py  # Multi-failure coordination
│   │   └── self_healing_ai.py     # Main AI interface
│   └── models/
│       ├── __init__.py
│       └── network.py             # Lightweight topology model
├── tests/
│   ├── test_failure_detection.py
│   ├── test_path_computation.py
│   ├── test_fast_reroute.py
│   └── test_integration.py
├── results/                       # Simulation output (PNG, JSON)
├── docs/
│   └── architecture.md
└── images/
    ├── architecture_diagram.png
    └── simulation_results.png
```

## Quick start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the 365-day simulation (baseline vs reactive vs proactive)
python src/simulation.py

# Run unit tests
cd tests && python -m pytest
# or individually:
python tests/test_path_computation.py
python tests/test_integration.py
```

## Results

The standalone simulation compares three configurations over 365 days:

| Metric | Baseline | Reactive | Proactive (FRR) |
|--------|----------|----------|------------------|
| Avg availability | ~97% | ~99% | ~99.5% |
| Recovery time | N/A (manual) | ~3 s | < 0.5 s |
| Downtime reduction | -- | ~50% | ~85% |

## Real Data center specifications

This project uses actual measurements from the THD Deggendorf

- **3 rooms**: 57.15 m², 67.94 m², 111.97 m²
- **Room heights**: 4.98 m, 7.53 m, 9.38 m
- **Cable types**: OM4 48F (intra-room), OS2 48F (inter-room)
- **Cable lengths**: 32 m / 34 m / 44 m (room-to-Main-Distribution)
- **Connectors**: LC dx Uniboot

## Dependencies

- Python 3.8+
- NumPy >= 1.21
- Matplotlib >= 3.5 (for plots)

## License

Academic use -- THD Deggendorf project.
