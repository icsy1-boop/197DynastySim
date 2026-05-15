# Qwen vLLM endpoint on VM A — set via environment variable or override here
import os

# VM A Qwen inference endpoint (OpenAI-compatible vLLM API)
qwen_endpoint = os.environ.get("QWEN_ENDPOINT", "http://localhost:8001")
qwen_model = os.environ.get("QWEN_MODEL", "Qwen/Qwen2.5-14B-Instruct")

# Legacy: openai_api_key kept so existing imports don't break.
# gpt_structure.py uses this only to set openai.api_key — we override the
# base URL to point at Qwen, so the value here doesn't matter.
openai_api_key = "not-used"

key_owner = "EEE197-Barangay"

maze_assets_loc = "../../environment/frontend_server/static_dirs/assets"
env_matrix = f"{maze_assets_loc}/barangay/matrix"
env_visuals = f"{maze_assets_loc}/barangay/visuals"

fs_storage = "../../environment/frontend_server/storage"
fs_temp_storage = "../../environment/frontend_server/temp_storage"

collision_block_id = "32125"

debug = True
