"""
Author: Joon Sung Park (joonspk@stanford.edu)
Modified for EEE 197 Barangay Simulation: redirects all LLM calls to a
local Qwen vLLM endpoint (OpenAI-compatible API on VM A) and uses a local
sentence-transformers model for embeddings instead of OpenAI ada-002.
"""
import json
import time

import openai
from utils import qwen_endpoint, qwen_model

# Point the openai client at the Qwen vLLM endpoint on VM A.
# vLLM serves an OpenAI-compatible API, so no other code changes are needed.
openai.api_key = "not-used"
openai.api_base = f"{qwen_endpoint}/v1"

# Lazy-loaded local embedding model (sentence-transformers, runs on VM B CPU).
_embed_model = None

def _get_embed_model():
  global _embed_model
  if _embed_model is None:
    from sentence_transformers import SentenceTransformer
    _embed_model = SentenceTransformer("all-MiniLM-L6-v2")
  return _embed_model


def temp_sleep(seconds=0.1):
  time.sleep(seconds)


def ChatGPT_single_request(prompt):
  temp_sleep()
  completion = openai.ChatCompletion.create(
    model=qwen_model,
    messages=[{"role": "user", "content": prompt}]
  )
  return completion["choices"][0]["message"]["content"]


# ============================================================================
# #####################[SECTION 1: CHAT STRUCTURE] ###########################
# ============================================================================

def GPT4_request(prompt):
  temp_sleep()
  try:
    completion = openai.ChatCompletion.create(
      model=qwen_model,
      messages=[{"role": "user", "content": prompt}]
    )
    return completion["choices"][0]["message"]["content"]
  except Exception as e:
    print(f"Qwen ERROR (GPT4_request): {e}")
    return "ChatGPT ERROR"


def ChatGPT_request(prompt):
  try:
    completion = openai.ChatCompletion.create(
      model=qwen_model,
      messages=[{"role": "user", "content": prompt}]
    )
    return completion["choices"][0]["message"]["content"]
  except Exception as e:
    print(f"Qwen ERROR (ChatGPT_request): {e}")
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
  """
  Calls the Qwen vLLM completions endpoint using openai-compatible params.
  The gpt_parameter dict keys match the original OpenAI Completion.create args.
  """
  temp_sleep()
  try:
    response = openai.Completion.create(
      model=qwen_model,
      prompt=prompt,
      temperature=gpt_parameter["temperature"],
      max_tokens=gpt_parameter["max_tokens"],
      top_p=gpt_parameter["top_p"],
      frequency_penalty=gpt_parameter["frequency_penalty"],
      presence_penalty=gpt_parameter["presence_penalty"],
      stream=gpt_parameter["stream"],
      stop=gpt_parameter["stop"],
    )
    return response.choices[0].text
  except Exception as e:
    print(f"TOKEN LIMIT EXCEEDED or Qwen error: {e}")
    return "TOKEN LIMIT EXCEEDED"


def generate_prompt(curr_input, prompt_lib_file):
  """
  Loads a prompt template file and substitutes !<INPUT N>! placeholders
  with the values from curr_input.
  """
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


def get_embedding(text, model="all-MiniLM-L6-v2"):
  """
  Returns a 384-dim embedding vector using a local sentence-transformers model
  running on VM B. This avoids any dependency on VM A for embeddings and is
  much cheaper than calling an LLM endpoint per memory node.
  """
  text = text.replace("\n", " ")
  if not text:
    text = "this is blank"
  embed_model = _get_embed_model()
  return embed_model.encode(text).tolist()
