import time
from openai import OpenAI

prompt = (
    "Here is a brief description of Maria Santos.\n"
    "Name: Maria Santos\nAge: 45\nInnate traits: honest, ambitious\n"
    "Currently: Maria Santos is focused on: manage barangay budget; attend council meetings.\n\n"
    "On the scale of 1 to 10, rate the likely poignancy of this event for Maria Santos.\n"
    "Event: budget meeting is being held\n"
    "Rate (return a number between 1 to 10):\n"
    'Output the response to the prompt above in json. '
    "The output should ONLY contain ONE integer value on the scale of 1 to 10.\n"
    'Example output json:\n{"output": "5"}'
)

endpoints = [
    ("Qwen3.6-27B (ours)",   "http://202.92.159.240:8007/v1", "Qwen/Qwen3.6-27B"),
    ("Huihui-4B (friend's)", "http://10.158.24.216:8001/v1",  "huihui-ai/Huihui-Qwen3.5-4B-abliterated"),
]

for label, base_url, model in endpoints:
    try:
        client = OpenAI(api_key="x", base_url=base_url)
        t0 = time.time()
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            max_tokens=50,
        )
        elapsed = time.time() - t0
        content = resp.choices[0].message.content.strip()
        print(f"[{label}]")
        print(f"  Time : {elapsed:.2f}s")
        print(f"  Reply: {content[:120]}")
        print()
    except Exception as e:
        print(f"[{label}] ERROR: {e}")
        print()
