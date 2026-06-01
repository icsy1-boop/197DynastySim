"""
Recomputes all embeddings.json files in a storage folder using the nomic
remote endpoint, replacing whatever-dim vectors with nomic 768-dim vectors.

Usage (run from reverie/backend_server/):
  python reembed_storage.py --sim base_barangay
"""
import json
import os
import argparse
from pathlib import Path
from openai import OpenAI

STORAGE_ROOT = "../../environment/frontend_server/storage"

endpoint = os.environ.get("EMBEDDING_ENDPOINT", "http://10.158.24.216:8002")
model    = os.environ.get("EMBEDDING_MODEL", "nomic-ai/nomic-embed-text-v1.5")
client   = OpenAI(api_key="ollama", base_url=f"{endpoint}/v1")

_cache = {}

def embed(text):
    text = text.replace("\n", " ").strip() or "this is blank"
    if text in _cache:
        return _cache[text]
    vec = client.embeddings.create(input=[text], model=model).data[0].embedding
    _cache[text] = vec
    return vec

def reembed_file(path: Path):
    with open(path) as f:
        data = json.load(f)
    if not data:
        return 0
    # Check if already 768-dim (skip if already migrated)
    sample = next(iter(data.values()))
    if isinstance(sample, list) and len(sample) == 768:
        return 0
    new_data = {key: embed(key) for key in data}
    with open(path, "w") as f:
        json.dump(new_data, f)
    return len(new_data)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sim", default="base_barangay")
    args = parser.parse_args()

    sim_path = Path(STORAGE_ROOT) / args.sim
    files = list(sim_path.rglob("embeddings.json"))
    print(f"Found {len(files)} embeddings.json files in {sim_path}")

    total = 0
    for i, f in enumerate(files):
        n = reembed_file(f)
        total += n
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(files)} files processed ({total} embeddings re-computed so far)")

    print(f"Done. {total} embeddings recomputed across {len(files)} files.")

if __name__ == "__main__":
    main()
