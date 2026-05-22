"""
export_memories.py

Reads all persona associative memory nodes from a simulation run and writes:
  output/barangay/memories.csv       — every memory node for every agent
  output/barangay/relationships.csv  — thought nodes that mention another agent

Run from reverie/backend_server/:
  python export_memories.py [--sim base_barangay] [--out ../../output/barangay]
"""
import argparse
import csv
import json
import os

STORAGE_ROOT = "../../environment/frontend_server/storage"
DEFAULT_OUTPUT = "../../../output/barangay"


def iter_nodes(storage_root, sim_name):
    """Yield (persona_name, node_dict) for every node in the simulation."""
    personas_dir = os.path.join(storage_root, sim_name, "personas")
    if not os.path.isdir(personas_dir):
        raise SystemExit(f"Personas dir not found: {personas_dir}")

    for persona_name in sorted(os.listdir(personas_dir)):
        nodes_path = os.path.join(
            personas_dir, persona_name,
            "bootstrap_memory", "associative_memory", "nodes.json")
        if not os.path.exists(nodes_path):
            continue
        with open(nodes_path, encoding="utf-8") as f:
            nodes = json.load(f)
        for node_id, node in nodes.items():
            yield persona_name, node_id, node


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sim", default="base_barangay")
    parser.add_argument("--out", default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    storage_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), STORAGE_ROOT))
    out_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), args.out))
    os.makedirs(out_dir, exist_ok=True)

    # Collect all agent names for relationship detection.
    personas_dir = os.path.join(storage_root, args.sim, "personas")
    agent_names = set(os.listdir(personas_dir)) if os.path.isdir(personas_dir) else set()

    mem_path = os.path.join(out_dir, "memories.csv")
    rel_path = os.path.join(out_dir, "relationships.csv")

    mem_fields = ["persona", "node_id", "type", "depth", "created",
                  "subject", "predicate", "object", "description",
                  "poignancy", "keywords"]
    rel_fields = ["persona", "node_id", "created", "subject", "predicate",
                  "object", "description", "poignancy", "mentioned_agent"]

    mem_count = rel_count = 0

    with open(mem_path, "w", newline="", encoding="utf-8") as mf, \
         open(rel_path, "w", newline="", encoding="utf-8") as rf:

        mw = csv.DictWriter(mf, fieldnames=mem_fields)
        rw = csv.DictWriter(rf, fieldnames=rel_fields)
        mw.writeheader()
        rw.writeheader()

        for persona_name, node_id, node in iter_nodes(storage_root, args.sim):
            keywords_str = "|".join(node.get("keywords", []))
            mw.writerow({
                "persona":     persona_name,
                "node_id":     node_id,
                "type":        node.get("type", ""),
                "depth":       node.get("depth", 0),
                "created":     node.get("created", ""),
                "subject":     node.get("subject", ""),
                "predicate":   node.get("predicate", ""),
                "object":      node.get("object", ""),
                "description": node.get("description", ""),
                "poignancy":   node.get("poignancy", 0),
                "keywords":    keywords_str,
            })
            mem_count += 1

            # Relationship row: thought nodes that mention a different agent.
            if node.get("type") == "thought":
                desc = node.get("description", "")
                obj  = node.get("object", "")
                for other in agent_names:
                    if other != persona_name and (
                            other in desc or other in obj):
                        rw.writerow({
                            "persona":        persona_name,
                            "node_id":        node_id,
                            "created":        node.get("created", ""),
                            "subject":        node.get("subject", ""),
                            "predicate":      node.get("predicate", ""),
                            "object":         obj,
                            "description":    desc,
                            "poignancy":      node.get("poignancy", 0),
                            "mentioned_agent": other,
                        })
                        rel_count += 1

    print(f"Wrote {mem_count:,} memory nodes  → {mem_path}")
    print(f"Wrote {rel_count:,} relationship rows → {rel_path}")


if __name__ == "__main__":
    main()
