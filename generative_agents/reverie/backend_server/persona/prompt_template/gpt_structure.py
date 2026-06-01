"""
Author: Joon Sung Park (joonspk@stanford.edu)
Modified for EEE 197 Barangay Simulation: redirects all LLM calls to the
institution's Qwen vLLM endpoint and uses the remote nomic-ai embedding
endpoint on VM A (10.158.24.216:8002) instead of local sentence-transformers.
"""
import json
import os
import re
import threading

import httpx
from openai import OpenAI
from utils import qwen_endpoint, qwen_model, embedding_endpoint, embedding_model

# Set QWEN_THINKING=1 to re-enable chain-of-thought (slower, higher quality).
_THINKING = os.environ.get("QWEN_THINKING", "0") == "1"
_NO_THINK = {} if _THINKING else {"extra_body": {"chat_template_kwargs": {"enable_thinking": False}}}


def _strip_qwen_thinking(text):
  """Remove Qwen reasoning-model artifacts before parsing."""
  text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
  lines = [l for l in text.split('\n')
           if l.strip() not in ('TOODOOOOOO', '-==- -==- -==-', '')]
  return '\n'.join(lines).strip()

def _make_http_client():
  """httpx client with no keep-alive to prevent CLOSE-WAIT hangs."""
  return httpx.Client(
    timeout=httpx.Timeout(180.0),
    limits=httpx.Limits(max_keepalive_connections=0, max_connections=None),
  )

# Primary client — institution's Qwen 27B (Tier-2 citizens).
_client = OpenAI(api_key="not-used", base_url=f"{qwen_endpoint}/v1",
                 http_client=_make_http_client())

# Secondary client — abliterated 4B on VM A (Tier-1 political agents).
_abliterated_endpoint = os.environ.get("ABLITERATED_ENDPOINT", "")
_abliterated_model    = os.environ.get("ABLITERATED_MODEL", "")
_client_abliterated   = (
    OpenAI(api_key="not-used", base_url=f"{_abliterated_endpoint}/v1",
           http_client=_make_http_client())
    if _abliterated_endpoint else None
)

# Embedding client — nomic-ai on VM A port 8002 (fully parallel, no local lock needed).
_embed_client = OpenAI(api_key="ollama", base_url=f"{embedding_endpoint}/v1",
                       http_client=_make_http_client())

# Thread-local tier routing.
_tier_local = threading.local()

def set_persona_tier(tier: int):
  _tier_local.agent_tier = tier

def set_force_tier(tier: int):
  _tier_local.force_tier = tier

def clear_force_tier():
  _tier_local.force_tier = None

def _get_client_and_model():
  tier = getattr(_tier_local, 'force_tier', None)
  if tier is None:
    tier = getattr(_tier_local, 'agent_tier', 2)
  if tier == 1 and _client_abliterated is not None and _abliterated_model:
    return _client_abliterated, _abliterated_model
  return _client, qwen_model


def temp_sleep(seconds=0.1):
  return  # no-op: local vLLM server, rate-limit sleep wastes wall time


def ChatGPT_single_request(prompt):
  temp_sleep()
  client, model = _get_client_and_model()
  completion = client.chat.completions.create(
    model=model,
    messages=[{"role": "user", "content": prompt}],
    **_NO_THINK
  )
  return _strip_qwen_thinking(completion.choices[0].message.content)


# ============================================================================
# #####################[SECTION 1: CHAT STRUCTURE] ###########################
# ============================================================================

def GPT4_request(prompt):
  temp_sleep()
  try:
    client, model = _get_client_and_model()
    completion = client.chat.completions.create(
      model=model,
      messages=[{"role": "user", "content": prompt}],
      **_NO_THINK
    )
    return _strip_qwen_thinking(completion.choices[0].message.content)
  except Exception as e:
    print(f"LLM ERROR (GPT4_request): {e}")
    return "ChatGPT ERROR"


def ChatGPT_request(prompt):
  try:
    client, model = _get_client_and_model()
    completion = client.chat.completions.create(
      model=model,
      messages=[{"role": "user", "content": prompt}],
      **_NO_THINK
    )
    return _strip_qwen_thinking(completion.choices[0].message.content)
  except Exception as e:
    print(f"LLM ERROR (ChatGPT_request): {e}")
    return "ChatGPT ERROR"


def GPT4_safe_generate_response(prompt,
                                example_output,
                                special_instruction,
                                repeat=3,
                                fail_safe_response="error",
                                func_validate=None,
                                func_clean_up=None,
                                verbose=False):
  prompt = '"""\n' + prompt + '\n"""\n'
  prompt += f"Output the response to the prompt above in json. {special_instruction}\n"
  prompt += "Example output json:\n"
  prompt += '{"output": "' + str(example_output) + '"}'

  if verbose:
    print("QWEN PROMPT")
    print(prompt)

  for i in range(repeat):
    try:
      curr_gpt_response = GPT4_request(prompt).strip()
      end_index = curr_gpt_response.rfind('}') + 1
      curr_gpt_response = curr_gpt_response[:end_index]
      curr_gpt_response = json.loads(curr_gpt_response)["output"]
      if func_validate(curr_gpt_response, prompt=prompt):
        return func_clean_up(curr_gpt_response, prompt=prompt)
      if verbose:
        print("---- repeat count:", i, curr_gpt_response)
    except:
      pass

  return False


def ChatGPT_safe_generate_response(prompt,
                                   example_output,
                                   special_instruction,
                                   repeat=3,
                                   fail_safe_response="error",
                                   func_validate=None,
                                   func_clean_up=None,
                                   verbose=False):
  prompt = '"""\n' + prompt + '\n"""\n'
  prompt += f"Output the response to the prompt above in json. {special_instruction}\n"
  prompt += "Example output json:\n"
  prompt += '{"output": "' + str(example_output) + '"}'

  if verbose:
    print("QWEN PROMPT")
    print(prompt)

  for i in range(repeat):
    try:
      curr_gpt_response = ChatGPT_request(prompt).strip()
      end_index = curr_gpt_response.rfind('}') + 1
      curr_gpt_response = curr_gpt_response[:end_index]
      curr_gpt_response = json.loads(curr_gpt_response)["output"]
      if func_validate(curr_gpt_response, prompt=prompt):
        return func_clean_up(curr_gpt_response, prompt=prompt)
      if verbose:
        print("---- repeat count:", i, curr_gpt_response)
    except:
      pass

  return False


def ChatGPT_safe_generate_response_OLD(prompt,
                                       repeat=3,
                                       fail_safe_response="error",
                                       func_validate=None,
                                       func_clean_up=None,
                                       verbose=False):
  if verbose:
    print("QWEN PROMPT")
    print(prompt)

  for i in range(repeat):
    try:
      curr_gpt_response = ChatGPT_request(prompt).strip()
      if func_validate(curr_gpt_response, prompt=prompt):
        return func_clean_up(curr_gpt_response, prompt=prompt)
      if verbose:
        print(f"---- repeat count: {i}")
        print(curr_gpt_response)
    except:
      pass
  print("FAIL SAFE TRIGGERED")
  return fail_safe_response


# ============================================================================
# ###################[SECTION 2: COMPLETION STRUCTURE] #######################
# ============================================================================

def GPT_request(prompt, gpt_parameter):
  temp_sleep()
  try:
    client, model = _get_client_and_model()
    response = client.completions.create(
      model=model,
      prompt=prompt,
      temperature=gpt_parameter["temperature"],
      max_tokens=gpt_parameter["max_tokens"],
      top_p=gpt_parameter["top_p"],
      frequency_penalty=gpt_parameter["frequency_penalty"],
      presence_penalty=gpt_parameter["presence_penalty"],
      stream=gpt_parameter["stream"],
      stop=gpt_parameter["stop"],
    )
    return _strip_qwen_thinking(response.choices[0].text)
  except Exception as e:
    print(f"TOKEN LIMIT EXCEEDED or Qwen error: {e}")
    return "TOKEN LIMIT EXCEEDED"


def generate_prompt(curr_input, prompt_lib_file):
  if type(curr_input) == type("string"):
    curr_input = [curr_input]
  curr_input = [str(i) for i in curr_input]

  f = open(prompt_lib_file, "r")
  prompt = f.read()
  f.close()
  for count, i in enumerate(curr_input):
    prompt = prompt.replace(f"!<INPUT {count}>!", i)
  if "<commentblockmarker>###</commentblockmarker>" in prompt:
    prompt = prompt.split("<commentblockmarker>###</commentblockmarker>")[1]
  return prompt.strip()


def safe_generate_response(prompt,
                           gpt_parameter,
                           repeat=5,
                           fail_safe_response="error",
                           func_validate=None,
                           func_clean_up=None,
                           verbose=False):
  if verbose:
    print(prompt)

  for i in range(repeat):
    curr_gpt_response = GPT_request(prompt, gpt_parameter)
    if func_validate(curr_gpt_response, prompt=prompt):
      return func_clean_up(curr_gpt_response, prompt=prompt)
    if verbose:
      print("---- repeat count:", i, curr_gpt_response)
  return fail_safe_response


_embedding_cache = {}

def get_embedding(text, model=None):
  """
  Returns an embedding via the remote nomic-ai endpoint on VM A (port 8002).
  Fully parallel — no local lock needed since it's just an HTTP call.
  """
  text = text.replace("\n", " ") or "this is blank"
  cache_key = (embedding_model, text)
  if cache_key in _embedding_cache:
    return _embedding_cache[cache_key]
  result = _embed_client.embeddings.create(
    input=[text], model=embedding_model
  ).data[0].embedding
  _embedding_cache[cache_key] = result
  return result
