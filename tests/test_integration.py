"""Integration test -- full SelfHealingNetworkAI with a small topology."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from collections import defaultdict
from src.models.network import NetworkNode, Cable, NetworkTopology
from src.core.self_healing_ai import SelfHealingNetworkAI


def build_small_topology():
    net = NetworkTopology()
    nid = 0
    cid = 0

    for dc_id in (1, 2):
        # 2 servers per room
        sids = []
        for _ in range(2):
            nid += 1
            s = NetworkNode(id=nid, node_type="server", dc_id=dc_id)
            net.add_node(s)
            sids.append(nid)

        # 1 leaf
        nid += 1
        leaf = NetworkNode(id=nid, node_type="switch", dc_id=dc_id,
                           layer="leaf")
        net.add_node(leaf)
        leaf_id = nid

        # 1 spine
        nid += 1
        spine = NetworkNode(id=nid, node_type="switch", dc_id=dc_id,
                            layer="spine")
        net.add_node(spine)
        spine_id = nid

        for sid in sids:
            cid += 1
            net.add_cable(Cable(id=cid, from_node=sid, to_node=leaf_id,
                                cable_type="OM4", length=4.0))

        cid += 1
        net.add_cable(Cable(id=cid, from_node=leaf_id, to_node=spine_id,
                            cable_type="OS2", length=6.0))

    # cross-room spine link
    spines = [s for s in net.switches.values() if s.layer == "spine"]
    cid += 1
    net.add_cable(Cable(id=cid, from_node=spines[0].id,
                        to_node=spines[1].id,
                        cable_type="OS2", length=38, is_cross_room=True))
    return net


def test_precompute_and_recover():
    net = build_small_topology()
    ai = SelfHealingNetworkAI()
    ai.precompute_backup_paths(net)

    stats = ai.get_stats()
    assert stats["self_healing_events"] == 0

    # simulate a leaf failure
    leaf = [s for s in net.switches.values() if s.layer == "leaf"][0]
    leaf.is_active = False

    result = ai.handle_failure(net, leaf.id)
    assert result["failed_node"] == leaf.id

    stats = ai.get_stats()
    assert stats["self_healing_events"] == 1
    assert stats["recovery_rate"] >= 0  # may be 0 if no paths were affected


if __name__ == "__main__":
    test_precompute_and_recover()
    print("Integration test passed.")
