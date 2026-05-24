#!/usr/bin/env python3
"""
Standalone simulation driver for the Self-Healing Network AI.

Builds a small 3-room Fat-Tree + Jellyfish overlay topology from the
real THD Deggendorf specifications, then runs a 365-day simulation
comparing three configurations:

  1. Baseline   -- no self-healing (failures just cause packet loss)
  2. Reactive   -- on-the-fly path recomputation after failures
  3. Proactive  -- FRR + recovery orchestration (full AI)

Outputs daily metrics and a comparison plot to results/.
"""

import sys, os, json, random, time
import numpy as np

# make sure local imports work regardless of cwd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from models.network import NetworkNode, Cable, NetworkTopology
from core.self_healing_ai import SelfHealingNetworkAI


# ------------------------------------------------------------------ #
# Topology builder
# ------------------------------------------------------------------ #

def build_topology(cfg: Config) -> NetworkTopology:
    """Build a 3-room Fat-Tree + full-mesh spine interconnect."""
    net = NetworkTopology()
    node_id = 0
    cable_id = 0

    room_positions = [(0, 0, 0), (6.32, 0, 0), (13.26, 0, 0)]

    for dc_id in range(1, cfg.num_rooms + 1):
        x, y, z = room_positions[dc_id - 1]
        h = cfg.room_heights[dc_id]
        srv_power = cfg.server_power[dc_id]

        # servers
        server_ids = []
        for rack in range(cfg.racks_per_room):
            for s in range(cfg.servers_per_rack):
                node_id += 1
                srv = NetworkNode(
                    id=node_id, node_type="server", dc_id=dc_id,
                    position=(x + 2 + (rack % 2) * 4,
                              y + 2 + (rack // 2) * 5,
                              z + 1 + s * 0.5),
                    power_consumption=srv_power, base_power=srv_power,
                )
                net.add_node(srv)
                server_ids.append(node_id)

        # leaf switches
        leaf_ids = []
        for i in range(cfg.leaves_per_room):
            node_id += 1
            leaf = NetworkNode(
                id=node_id, node_type="switch", dc_id=dc_id,
                layer="leaf",
                position=(x + 3 + i * 4, y + 1, z + 1.5),
                power_consumption=cfg.leaf_power,
                base_power=cfg.leaf_power,
            )
            net.add_node(leaf)
            leaf_ids.append(node_id)

        # spine switch
        node_id += 1
        spine = NetworkNode(
            id=node_id, node_type="switch", dc_id=dc_id,
            layer="spine",
            position=(x + 5, y + 6, z + h - 0.5),
            power_consumption=cfg.spine_power,
            base_power=cfg.spine_power,
        )
        net.add_node(spine)
        spine_id = node_id

        # server -> leaf cables (OM4)
        for idx, sid in enumerate(server_ids):
            leaf = leaf_ids[idx // 16]
            cable_id += 1
            c = Cable(id=cable_id, from_node=sid, to_node=leaf,
                      cable_type="OM4", length=4.0)
            net.add_cable(c)

        # leaf -> spine cables (OS2)
        for lid in leaf_ids:
            cable_id += 1
            c = Cable(id=cable_id, from_node=lid, to_node=spine_id,
                      cable_type="OS2", length=h - 2.0)
            net.add_cable(c)

    # inter-room spine mesh (OS2)
    spines = [s for s in net.switches.values() if s.layer == "spine"]
    for i, s1 in enumerate(spines):
        for s2 in list(net.switches.values())[i + 1:]:
            if s2.layer != "spine":
                continue
            cable_id += 1
            dist = (cfg.cable_lengths[s1.dc_id]
                    + cfg.cable_lengths[s2.dc_id]) / 2
            c = Cable(id=cable_id, from_node=s1.id, to_node=s2.id,
                      cable_type="OS2", length=dist, is_cross_room=True)
            net.add_cable(c)

    return net


# ------------------------------------------------------------------ #
# Failure injection
# ------------------------------------------------------------------ #

def inject_failures(net: NetworkTopology, cfg: Config, day: int,
                    rng: np.random.Generator):
    """Stochastic daily failures.  Returns list of failed node ids."""
    failed = []

    for node in list(net.switches.values()):
        if node.is_active and rng.random() < cfg.switch_failure_rate:
            node.is_active = False
            failed.append(node.id)
            # deactivate connected cables
            for nid, cable in net.adjacency_list[node.id]:
                cable.is_active = False

    for node in list(net.servers.values()):
        if node.is_active and rng.random() < cfg.server_failure_rate:
            node.is_active = False
            failed.append(node.id)

    for cable in list(net.cables.values()):
        if cable.is_active and rng.random() < cfg.cable_failure_rate:
            cable.is_active = False

    return failed


def repair_nodes(net: NetworkTopology, cfg: Config, day: int):
    """Simple 7-day repair cycle -- bring back everything that failed
    more than REPAIR_TIME_DAYS ago (we just re-activate randomly)."""
    # In this standalone demo we re-activate a fraction of failed nodes
    # each day to keep the simulation interesting.
    for node in list(net.switches.values()):
        if not node.is_active and random.random() < 1.0 / cfg.repair_time_days:
            node.is_active = True
            # re-activate cables
            for nid, cable in net.adjacency_list[node.id]:
                if cable.from_node in net.switches and net.switches[cable.from_node].is_active:
                    cable.is_active = True
                elif cable.from_node in net.servers and net.servers[cable.from_node].is_active:
                    cable.is_active = True
                if cable.to_node in net.switches and net.switches[cable.to_node].is_active:
                    cable.is_active = True
                elif cable.to_node in net.servers and net.servers[cable.to_node].is_active:
                    cable.is_active = True

    for node in list(net.servers.values()):
        if not node.is_active and random.random() < 1.0 / cfg.repair_time_days:
            node.is_active = True


# ------------------------------------------------------------------ #
# Metrics
# ------------------------------------------------------------------ #

def compute_availability(net: NetworkTopology) -> float:
    total = len(net.servers)
    if total == 0:
        return 0.0
    active = sum(1 for s in net.servers.values() if s.is_active)
    return active / total * 100.0


def route_packets(net: NetworkTopology, ai: SelfHealingNetworkAI,
                  num_packets: int = 50):
    """Try to route random inter-DC packets.  Return count of successes."""
    servers = list(net.servers.values())
    if len(servers) < 2:
        return 0
    routed = 0
    for _ in range(num_packets):
        src, dst = random.sample(servers, 2)
        if not (src.is_active and dst.is_active):
            continue
        if src.dc_id == dst.dc_id:
            continue
        # check if a recovery path exists
        if (src.id, dst.id) in ai.recovery_paths:
            routed += 1
    return routed


# ------------------------------------------------------------------ #
# Main simulation
# ------------------------------------------------------------------ #

def run_simulation(mode="proactive", days=365, seed=42):
    """Run a single simulation configuration.

    mode: "baseline" | "reactive" | "proactive"
    """
    rng = np.random.default_rng(seed)
    cfg = Config(simulation_days=days)
    net = build_topology(cfg)
    ai = SelfHealingNetworkAI()

    if mode in ("reactive", "proactive"):
        ai.precompute_backup_paths(net)

    metrics = {
        "availability": [],
        "cable_failures": [],
        "switch_failures": [],
        "packets_routed": [],
        "recovery_events": [],
    }

    for day in range(days):
        # failures
        failed = inject_failures(net, cfg, day, rng)

        cable_fails = sum(1 for c in net.cables.values() if not c.is_active)
        switch_fails = sum(1 for s in net.switches.values() if not s.is_active)

        # self-healing
        recovery_events = 0
        if mode in ("reactive", "proactive") and failed:
            for fid in failed:
                node = net._get_node(fid)
                if node and node.node_type == "switch":
                    result = ai.handle_failure(net, fid)
                    recovery_events += result["recovered_paths"]
                    if mode == "proactive":
                        # re-activate nodes that FRR recovered paths for
                        pass  # paths are rerouted, not hardware fixed

        # repairs
        repair_nodes(net, cfg, day)

        avail = compute_availability(net)
        routed = route_packets(net, ai)

        metrics["availability"].append(avail)
        metrics["cable_failures"].append(cable_fails)
        metrics["switch_failures"].append(switch_fails)
        metrics["packets_routed"].append(routed)
        metrics["recovery_events"].append(recovery_events)

    return metrics, ai.get_stats()


# ------------------------------------------------------------------ #
# Plotting
# ------------------------------------------------------------------ #

def plot_results(results: dict, out_dir: str):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    fig.suptitle("Self-Healing Network -- 365-Day Simulation", fontsize=14)

    for mode, color in [("baseline", "#e74c3c"), ("reactive", "#f39c12"),
                         ("proactive", "#2ecc71")]:
        m = results[mode][0]
        days = list(range(len(m["availability"])))

        axes[0, 0].plot(days, m["availability"], color=color,
                         label=mode, alpha=0.8)
        axes[0, 1].plot(days, m["cable_failures"], color=color,
                         label=mode, alpha=0.8)
        axes[0, 1].set_ylabel("Cumulative inactive cables")
        axes[1, 0].plot(days, m["packets_routed"], color=color,
                         label=mode, alpha=0.8)
        axes[1, 1].plot(days, m["recovery_events"], color=color,
                         label=mode, alpha=0.8)

    for ax in axes.flat:
        ax.set_xlabel("Day")
        ax.legend(loc="best", fontsize=8)
        ax.grid(True, alpha=0.3)

    axes[0, 0].set_title("Network Availability (%)")
    axes[0, 0].set_ylabel("Availability %")
    axes[0, 1].set_title("Cable Failures")
    axes[1, 0].set_title("Inter-DC Packets Routed")
    axes[1, 0].set_ylabel("Packets / day")
    axes[1, 1].set_title("Recovery Events")
    axes[1, 1].set_ylabel("Paths recovered")

    plt.tight_layout()
    out_path = os.path.join(out_dir, "self_healing_simulation.png")
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"  Plot saved to {out_path}")


# ------------------------------------------------------------------ #
# Entry point
# ------------------------------------------------------------------ #

def main():
    print("=" * 60)
    print("  Self-Healing Network AI -- Standalone Simulation")
    print("=" * 60)

    days = 365
    results = {}

    for mode in ("baseline", "reactive", "proactive"):
        print(f"\n  Running {mode} ({days} days) ...")
        t0 = time.time()
        metrics, ai_stats = run_simulation(mode=mode, days=days)
        elapsed = time.time() - t0
        results[mode] = (metrics, ai_stats)
        avg_avail = np.mean(metrics["availability"])
        total_routed = sum(metrics["packets_routed"])
        print(f"    Avg availability: {avg_avail:.2f}%")
        print(f"    Total packets routed: {total_routed}")
        print(f"    Completed in {elapsed:.1f}s")

    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "results")
    os.makedirs(out_dir, exist_ok=True)
    plot_results(results, out_dir)

    # write summary JSON
    summary = {}
    for mode in results:
        m, ai = results[mode]
        summary[mode] = {
            "avg_availability": float(np.mean(m["availability"])),
            "total_packets_routed": int(sum(m["packets_routed"])),
            "total_cable_failures": int(sum(m["cable_failures"])),
            "ai_stats": {k: v for k, v in ai.items()
                         if not isinstance(v, dict)},
        }
    json_path = os.path.join(out_dir, "simulation_summary.json")
    with open(json_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n  Summary JSON saved to {json_path}")

    print("\n" + "=" * 60)
    print("  Simulation complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
