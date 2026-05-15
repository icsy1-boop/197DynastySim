"""
export_barangay_csv.py

Reads a completed/in-progress generative_agents simulation storage directory
and exports two CSVs:
  - memories.csv     : every memory node from all agent associative memories
  - relationships.csv: every relationship (chat) between agents

Run from reverie/backend_server/:
  python export_barangay_csv.py [--sim SIM_NAME] [--out OUTPUT_DIR]

Defaults:
  --sim  base_barangay
  --out  ../../../output/barangay
"""
import json
import os
import csv
import argparse

FS_STORAGE = os.path.abspath(os.path.join(
    os.path.dirname(__file__),
    "../../environment/frontend_server/storage"
))


def export_memories(sim_folder, out_dir):
    """
    Reads each persona's associative_memory/nodes.json and writes one row per
    memory node to memories.csv.
    """
    personas_dir = os.path.join(sim_folder, "personas")
    if not os.path.isdir(personas_dir):
        print(f"  [skip] no personas dir at {personas_dir}")
        return 0

    out_file = os.path.join(out_dir, "memories.csv")
    rows_written = 0

    with open(out_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "agent_name", "node_id", "type", "depth",
            "created", "expiration",
            "subject", "predicate", "object",
            "description", "poignancy", "keywords"
        ])

        for persona_name in sorted(os.listdir(personas_dir)):
            # Look in both bootstrap_memory (initial) and current memory location
            candidate_dirs = [
                os.path.join(personas_dir, persona_name, "bootstrap_memory", "associative_memory"),
                os.path.join(personas_dir, persona_name, "associative_memory"),
            ]
            nodes_file = None
            for d in candidate_dirs:
                candidate = os.path.join(d, "nodes.json")
                if os.path.exists(candidate):
                    nodes_file = candidate
                    break

            if not nodes_file:
                continue

            nodes = json.load(open(nodes_file))
            for node_id, node in nodes.items():
                writer.writerow([
                    persona_name,
                    node_id,
                    node.get("type", ""),
                    node.get("depth", ""),
                    node.get("created", ""),
                    node.get("expiration", "") or "",
                    node.get("subject", ""),
                    node.get("predicate", ""),
                    node.get("object", ""),
                    node.get("description", ""),
                    node.get("poignancy", ""),
                    "|".join(node.get("keywords", [])),
                ])
                rows_written += 1

    print(f"  memories.csv: {rows_written} rows -> {out_file}")
    return rows_written


def export_relationships(sim_folder, out_dir):
    """
    Extracts chat-type memory nodes (which represent actual conversations
    between agents) and writes them to relationships.csv.
    Also extracts any 'thought' nodes whose subject-object pair represents
    a relationship summary (predicate contains 'relationship' or 'trust').
    """
    personas_dir = os.path.join(sim_folder, "personas")
    if not os.path.isdir(personas_dir):
        print(f"  [skip] no personas dir at {personas_dir}")
        return 0

    out_file = os.path.join(out_dir, "relationships.csv")
    rows_written = 0

    with open(out_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "from_agent", "to_agent", "relation_type",
            "predicate", "description", "created", "poignancy"
        ])

        for persona_name in sorted(os.listdir(personas_dir)):
            candidate_dirs = [
                os.path.join(personas_dir, persona_name, "bootstrap_memory", "associative_memory"),
                os.path.join(personas_dir, persona_name, "associative_memory"),
            ]
            nodes_file = None
            for d in candidate_dirs:
                candidate = os.path.join(d, "nodes.json")
                if os.path.exists(candidate):
                    nodes_file = candidate
                    break

            if not nodes_file:
                continue

            nodes = json.load(open(nodes_file))
            for node_id, node in nodes.items():
                ntype = node.get("type", "")
                pred  = node.get("predicate", "").lower()
                subj  = node.get("subject", "")
                obj   = node.get("object", "")

                # Chat nodes: direct conversation records
                if ntype == "chat":
                    writer.writerow([
                        persona_name, obj, "chat",
                        pred,
                        node.get("description", ""),
                        node.get("created", ""),
                        node.get("poignancy", ""),
                    ])
                    rows_written += 1

                # Thought nodes that describe a relationship
                elif ntype == "thought" and any(kw in pred for kw in
                        ("relation", "trust", "family", "ally", "friend",
                         "knows", "feels about")):
                    writer.writerow([
                        subj, obj, "thought",
                        pred,
                        node.get("description", ""),
                        node.get("created", ""),
                        node.get("poignancy", ""),
                    ])
                    rows_written += 1

    print(f"  relationships.csv: {rows_written} rows -> {out_file}")
    return rows_written


def main():
    parser = argparse.ArgumentParser(description="Export barangay simulation to CSV")
    parser.add_argument("--sim", default="base_barangay",
                        help="Simulation name in storage/ (default: base_barangay)")
    parser.add_argument("--out", default=None,
                        help="Output directory (default: ../../../output/barangay)")
    args = parser.parse_args()

    sim_folder = os.path.join(FS_STORAGE, args.sim)
    if not os.path.isdir(sim_folder):
        print(f"ERROR: simulation folder not found: {sim_folder}")
        return

    out_dir = args.out or os.path.abspath(os.path.join(
        os.path.dirname(__file__), "../../../output/barangay"))
    os.makedirs(out_dir, exist_ok=True)

    print(f"Exporting simulation '{args.sim}' -> {out_dir}")
    export_memories(sim_folder, out_dir)
    export_relationships(sim_folder, out_dir)
    print("Done.")


if __name__ == "__main__":
    main()
