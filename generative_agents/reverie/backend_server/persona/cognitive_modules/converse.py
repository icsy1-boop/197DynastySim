"""
Author: Joon Sung Park (joonspk@stanford.edu)

File: converse.py
Description: An extra cognitive module for generating conversations. 
"""
import math
import os
import sys
import datetime
import random
sys.path.append('../')

# Conversations run up to this many back-and-forth turns. Lower = cheaper steps.
_CONVO_MAX_TURNS = int(os.environ.get("CONVO_MAX_TURNS", 4))

from global_methods import *

from persona.memory_structures.spatial_memory import *
from persona.memory_structures.associative_memory import *
from persona.memory_structures.scratch import *
from persona.cognitive_modules.retrieve import *
from persona.prompt_template.run_gpt_prompt import *

def generate_agent_chat_summarize_ideas(init_persona, 
                                        target_persona, 
                                        retrieved, 
                                        curr_context): 
  all_embedding_keys = list()
  for key, val in retrieved.items(): 
    for i in val: 
      all_embedding_keys += [i.embedding_key]
  all_embedding_key_str =""
  for i in all_embedding_keys: 
    all_embedding_key_str += f"{i}\n"

  try: 
    summarized_idea = run_gpt_prompt_agent_chat_summarize_ideas(init_persona,
                        target_persona, all_embedding_key_str, 
                        curr_context)[0]
  except:
    summarized_idea = ""
  return summarized_idea


def generate_summarize_agent_relationship(init_persona, 
                                          target_persona, 
                                          retrieved): 
  all_embedding_keys = list()
  for key, val in retrieved.items(): 
    for i in val: 
      all_embedding_keys += [i.embedding_key]
  all_embedding_key_str =""
  for i in all_embedding_keys: 
    all_embedding_key_str += f"{i}\n"

  summarized_relationship = run_gpt_prompt_agent_chat_summarize_relationship(
                              init_persona, target_persona,
                              all_embedding_key_str)[0]
  return summarized_relationship


def generate_agent_chat(maze, 
                        init_persona, 
                        target_persona,
                        curr_context, 
                        init_summ_idea, 
                        target_summ_idea): 
  summarized_idea = run_gpt_prompt_agent_chat(maze, 
                                              init_persona, 
                                              target_persona,
                                              curr_context, 
                                              init_summ_idea, 
                                              target_summ_idea)[0]
  for i in summarized_idea: 
    print (i)
  return summarized_idea


def agent_chat_v1(maze, init_persona, target_persona): 
  # Chat version optimized for speed via batch generation
  curr_context = (f"{init_persona.scratch.name} " + 
              f"was {init_persona.scratch.act_description} " + 
              f"when {init_persona.scratch.name} " + 
              f"saw {target_persona.scratch.name} " + 
              f"in the middle of {target_persona.scratch.act_description}.\n")
  curr_context += (f"{init_persona.scratch.name} " +
              f"is thinking of initating a conversation with " +
              f"{target_persona.scratch.name}.")

  summarized_ideas = []
  part_pairs = [(init_persona, target_persona), 
                (target_persona, init_persona)]
  for p_1, p_2 in part_pairs: 
    focal_points = [f"{p_2.scratch.name}"]
    retrieved = new_retrieve(p_1, focal_points, 50)
    relationship = generate_summarize_agent_relationship(p_1, p_2, retrieved)
    focal_points = [f"{relationship}", 
                    f"{p_2.scratch.name} is {p_2.scratch.act_description}"]
    retrieved = new_retrieve(p_1, focal_points, 25)
    summarized_idea = generate_agent_chat_summarize_ideas(p_1, p_2, retrieved, curr_context)
    summarized_ideas += [summarized_idea]

  return generate_agent_chat(maze, init_persona, target_persona, 
                      curr_context, 
                      summarized_ideas[0], 
                      summarized_ideas[1])


def generate_one_utterance(maze, init_persona, target_persona, retrieved, curr_chat): 
  # Chat version optimized for speed via batch generation
  curr_context = (f"{init_persona.scratch.name} " + 
              f"was {init_persona.scratch.act_description} " + 
              f"when {init_persona.scratch.name} " + 
              f"saw {target_persona.scratch.name} " + 
              f"in the middle of {target_persona.scratch.act_description}.\n")
  curr_context += (f"{init_persona.scratch.name} " +
              f"is initiating a conversation with " +
              f"{target_persona.scratch.name}.")

  x = run_gpt_generate_iterative_chat_utt(maze, init_persona, target_persona, retrieved, curr_context, curr_chat)[0]

  return x["utterance"], x["end"]

def agent_chat_v2(maze, init_persona, target_persona):
  curr_chat = []

  # A persona's view of the other is stable across a single conversation, so we
  # summarize each relationship ONCE up front rather than regenerating it every
  # turn (the original ran an LLM call + a 50-node retrieval per speaker per
  # turn). Combined with the turn cap this is the main per-step cost reduction.
  retrieved = new_retrieve(init_persona, [f"{target_persona.scratch.name}"], 50)
  rel_init = generate_summarize_agent_relationship(init_persona, target_persona, retrieved)
  retrieved = new_retrieve(target_persona, [f"{init_persona.scratch.name}"], 50)
  rel_target = generate_summarize_agent_relationship(target_persona, init_persona, retrieved)

  for i in range(_CONVO_MAX_TURNS):
    last_chat = ""
    for c in curr_chat[-4:]:
      last_chat += ": ".join(c) + "\n"
    if last_chat:
      focal_points = [f"{rel_init}",
                      f"{target_persona.scratch.name} is {target_persona.scratch.act_description}",
                      last_chat]
    else:
      focal_points = [f"{rel_init}",
                      f"{target_persona.scratch.name} is {target_persona.scratch.act_description}"]
    retrieved = new_retrieve(init_persona, focal_points, 15)
    utt, end = generate_one_utterance(maze, init_persona, target_persona, retrieved, curr_chat)

    curr_chat += [[init_persona.scratch.name, utt]]
    if end:
      break


    last_chat = ""
    for c in curr_chat[-4:]:
      last_chat += ": ".join(c) + "\n"
    if last_chat:
      focal_points = [f"{rel_target}",
                      f"{init_persona.scratch.name} is {init_persona.scratch.act_description}",
                      last_chat]
    else:
      focal_points = [f"{rel_target}",
                      f"{init_persona.scratch.name} is {init_persona.scratch.act_description}"]
    retrieved = new_retrieve(target_persona, focal_points, 15)
    utt, end = generate_one_utterance(maze, target_persona, init_persona, retrieved, curr_chat)

    curr_chat += [[target_persona.scratch.name, utt]]
    if end:
      break

  return curr_chat


def _salient_memories(persona, k=5, window_hours=120):
  """The agent's genuine top-of-mind: their most poignant RECENT memories,
  independent of who they're talking to. This is the substrate that lets anger
  (or loyalty) emerge naturally in conversation — a resident carrying a fresh
  poignancy-9 'ghost project SCANDAL' memory brings it up unprompted, while an
  insider carries defensive ones. Without this, the conversation only retrieves
  memories matching the partner's NAME, so world grievances stay buried.
  Returns a list of description strings (highest poignancy first)."""
  curr = getattr(persona.scratch, "curr_time", None)
  nodes = list(persona.a_mem.seq_event) + list(persona.a_mem.seq_thought)
  recent = []
  for n in nodes:
    if curr is not None and n.created is not None:
      if (curr - n.created).total_seconds() > window_hours * 3600:
        continue
    recent.append(n)
  # Strongest first; break ties by most recent. Skip idle filler + dedupe.
  recent.sort(key=lambda n: (n.poignancy, n.created or 0), reverse=True)
  out, seen = [], set()
  for n in recent:
    desc = (n.description or "").strip()
    if not desc or "idle" in (n.embedding_key or "") or desc in seen:
      continue
    seen.add(desc)
    out.append(desc)
    if len(out) >= k:
      break
  return out


def agent_chat_v3(maze, init_persona, target_persona):
  # One-shot conversation: generate the ENTIRE back-and-forth in a single LLM
  # call, vs agent_chat_v2's up-to-(2*_CONVO_MAX_TURNS) serial utterance calls.
  # Endpoints are fast and VM B is idle, so the per-step bottleneck is the serial
  # depth of conversation turns; collapsing them to one call is the main lever.
  # Grounded by a per-persona relationship summary, a partner-keyed memory
  # retrieval, AND each speaker's salient top-of-mind memories so their genuine
  # feelings (grievance, anger, loyalty) emerge instead of default pleasantries.
  curr_context = (f"{init_persona.scratch.name} "
              f"was {init_persona.scratch.act_description} "
              f"when {init_persona.scratch.name} "
              f"saw {target_persona.scratch.name} "
              f"in the middle of {target_persona.scratch.act_description}. "
              f"{init_persona.scratch.name} initiates a conversation with "
              f"{target_persona.scratch.name}.")

  retrieved_init = new_retrieve(init_persona, [f"{target_persona.scratch.name}"], 50)
  rel_init = generate_summarize_agent_relationship(init_persona, target_persona, retrieved_init)
  retrieved_target = new_retrieve(target_persona, [f"{init_persona.scratch.name}"], 50)
  rel_target = generate_summarize_agent_relationship(target_persona, init_persona, retrieved_target)

  salient_init = _salient_memories(init_persona)
  salient_target = _salient_memories(target_persona)

  convo = run_gpt_generate_whole_chat(
      maze, init_persona, target_persona,
      retrieved_init, retrieved_target, rel_init, rel_target,
      curr_context, max_turns=_CONVO_MAX_TURNS,
      salient_init=salient_init, salient_target=salient_target)
  return convo






def generate_summarize_ideas(persona, nodes, question): 
  statements = ""
  for n in nodes:
    statements += f"{n.embedding_key}\n"
  summarized_idea = run_gpt_prompt_summarize_ideas(persona, statements, question)[0]
  return summarized_idea


def generate_next_line(persona, interlocutor_desc, curr_convo, summarized_idea):
  # Original chat -- line by line generation 
  prev_convo = ""
  for row in curr_convo: 
    prev_convo += f'{row[0]}: {row[1]}\n'

  next_line = run_gpt_prompt_generate_next_convo_line(persona, 
                                                      interlocutor_desc, 
                                                      prev_convo, 
                                                      summarized_idea)[0]  
  return next_line


def generate_inner_thought(persona, whisper):
  inner_thought = run_gpt_prompt_generate_whisper_inner_thought(persona, whisper)[0]
  return inner_thought

def generate_action_event_triple(act_desp, persona): 
  """TODO 

  INPUT: 
    act_desp: the description of the action (e.g., "sleeping")
    persona: The Persona class instance
  OUTPUT: 
    a string of emoji that translates action description.
  EXAMPLE OUTPUT: 
    "🧈🍞"
  """
  if debug: print ("GNS FUNCTION: <generate_action_event_triple>")
  return run_gpt_prompt_event_triple(act_desp, persona)[0]


def generate_poig_score(persona, event_type, description): 
  if debug: print ("GNS FUNCTION: <generate_poig_score>")

  if "is idle" in description: 
    return 1

  if event_type == "event" or event_type == "thought": 
    return run_gpt_prompt_event_poignancy(persona, description)[0]
  elif event_type == "chat": 
    return run_gpt_prompt_chat_poignancy(persona, 
                           persona.scratch.act_description)[0]


def load_history_via_whisper(personas, whispers):
  for count, row in enumerate(whispers): 
    persona = personas[row[0]]
    whisper = row[1]

    thought = generate_inner_thought(persona, whisper)

    created = persona.scratch.curr_time
    expiration = persona.scratch.curr_time + datetime.timedelta(days=30)
    s, p, o = generate_action_event_triple(thought, persona)
    keywords = set([s, p, o])
    thought_poignancy = generate_poig_score(persona, "event", whisper)
    thought_embedding_pair = (thought, get_embedding(thought))
    persona.a_mem.add_thought(created, expiration, s, p, o, 
                              thought, keywords, thought_poignancy, 
                              thought_embedding_pair, None)


def open_convo_session(persona, convo_mode): 
  if convo_mode == "analysis": 
    curr_convo = []
    interlocutor_desc = "Interviewer"

    while True: 
      line = input("Enter Input: ")
      if line == "end_convo": 
        break

      if int(run_gpt_generate_safety_score(persona, line)[0]) >= 8: 
        print (f"{persona.scratch.name} is a computational agent, and as such, it may be inappropriate to attribute human agency to the agent in your communication.")        

      else: 
        retrieved = new_retrieve(persona, [line], 50)[line]
        summarized_idea = generate_summarize_ideas(persona, retrieved, line)
        curr_convo += [[interlocutor_desc, line]]

        next_line = generate_next_line(persona, interlocutor_desc, curr_convo, summarized_idea)
        curr_convo += [[persona.scratch.name, next_line]]


  elif convo_mode == "whisper": 
    whisper = input("Enter Input: ")
    thought = generate_inner_thought(persona, whisper)

    created = persona.scratch.curr_time
    expiration = persona.scratch.curr_time + datetime.timedelta(days=30)
    s, p, o = generate_action_event_triple(thought, persona)
    keywords = set([s, p, o])
    thought_poignancy = generate_poig_score(persona, "event", whisper)
    thought_embedding_pair = (thought, get_embedding(thought))
    persona.a_mem.add_thought(created, expiration, s, p, o, 
                              thought, keywords, thought_poignancy, 
                              thought_embedding_pair, None)
































