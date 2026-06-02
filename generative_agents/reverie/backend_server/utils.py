# LLM and embedding endpoints — set via environment variables
import os

# Institution's Qwen inference endpoint (Tier-2 citizens, 27B)
qwen_endpoint = os.environ.get("QWEN_ENDPOINT", "http://localhost:8015")
qwen_model = os.environ.get("QWEN_MODEL", "huihui-ai/Huihui-Qwen3.5-0.8B-abliterated")

# Embedding endpoint (nomic-ai on VM A, port 8002)
embedding_endpoint = os.environ.get("EMBEDDING_ENDPOINT", "http://localhost:11434")
embedding_model = os.environ.get("EMBEDDING_MODEL", "nomic-embed-text")

openai_api_model = "huihui-ai/Huihui-Qwen3.5-0.8B-abliterated"

openai_api_key = "not-used"

key_owner = "EEE197-Barangay"

maze_assets_loc = "../../environment/frontend_server/static_dirs/assets"
env_matrix = f"{maze_assets_loc}/barangay/matrix"
env_visuals = f"{maze_assets_loc}/barangay/visuals"

fs_storage = "../../environment/frontend_server/storage"
fs_temp_storage = "../../environment/frontend_server/temp_storage"

collision_block_id = "0"

debug = True
