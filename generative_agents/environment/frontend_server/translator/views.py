"""
Author: Joon Sung Park (joonspk@stanford.edu)
File: views.py
"""
import os
import string
import random
import json
from os import listdir
import os

import datetime
from django.shortcuts import render, redirect, HttpResponseRedirect
from django.http import HttpResponse, JsonResponse
from global_methods import *

from django.templatetags.static import static
from .models import *

def landing(request): 
  context = {}
  template = "landing/landing.html"
  return render(request, template, context)


def demo(request, sim_code, step, play_speed="2"): 
  move_file = f"compressed_storage/{sim_code}/master_movement.json"
  meta_file = f"compressed_storage/{sim_code}/meta.json"
  step = int(step)
  play_speed_opt = {"1": 1, "2": 2, "3": 4,
                    "4": 8, "5": 16, "6": 32}
  if play_speed not in play_speed_opt: play_speed = 2
  else: play_speed = play_speed_opt[play_speed]

  # Loading the basic meta information about the simulation.
  meta = dict() 
  with open (meta_file) as json_file: 
    meta = json.load(json_file)

  sec_per_step = meta["sec_per_step"]
  start_datetime = datetime.datetime.strptime(meta["start_date"] + " 00:00:00", 
                                              '%B %d, %Y %H:%M:%S')
  for i in range(step): 
    start_datetime += datetime.timedelta(seconds=sec_per_step)
  start_datetime = start_datetime.strftime("%Y-%m-%dT%H:%M:%S")

  # Loading the movement file
  raw_all_movement = dict()
  with open(move_file) as json_file: 
    raw_all_movement = json.load(json_file)
 
  # Loading all names of the personas
  persona_names = dict()
  persona_names = []
  persona_names_set = set()
  for p in list(raw_all_movement["0"].keys()): 
    persona_names += [{"original": p, 
                       "underscore": p.replace(" ", "_"), 
                       "initial": p[0] + p.split(" ")[-1][0]}]
    persona_names_set.add(p)

  # <all_movement> is the main movement variable that we are passing to the 
  # frontend. Whereas we use ajax scheme to communicate steps to the frontend
  # during the simulation stage, for this demo, we send all movement 
  # information in one step. 
  all_movement = dict()

  # Preparing the initial step. 
  # <init_prep> sets the locations and descriptions of all agents at the
  # beginning of the demo determined by <step>. 
  init_prep = dict() 
  for int_key in range(step+1): 
    key = str(int_key)
    val = raw_all_movement[key]
    for p in persona_names_set: 
      if p in val: 
        init_prep[p] = val[p]
  persona_init_pos = dict()
  for p in persona_names_set: 
    persona_init_pos[p.replace(" ","_")] = init_prep[p]["movement"]
  all_movement[step] = init_prep

  # Finish loading <all_movement>
  for int_key in range(step+1, len(raw_all_movement.keys())): 
    all_movement[int_key] = raw_all_movement[str(int_key)]

  context = {"sim_code": sim_code,
             "step": step,
             "persona_names": persona_names,
             "persona_init_pos": json.dumps(persona_init_pos), 
             "all_movement": json.dumps(all_movement), 
             "start_datetime": start_datetime,
             "sec_per_step": sec_per_step,
             "play_speed": play_speed,
             "mode": "demo"}
  template = "demo/demo.html"

  return render(request, template, context)


def UIST_Demo(request): 
  return demo(request, "March20_the_ville_n25_UIST_RUN-step-1-141", 2160, play_speed="3")


def home(request):
  f_curr_step = "temp_storage/curr_step.json"

  # Priority: ?sim= query param > DEFAULT_SIM_CODE env var > curr_sim_code.json file
  sim_code = (request.GET.get('sim')
              or os.environ.get('DEFAULT_SIM_CODE'))
  if not sim_code:
    f_curr_sim_code = "temp_storage/curr_sim_code.json"
    if not check_if_file_exists(f_curr_sim_code):
      context = {}
      template = "home/error_start_backend.html"
      return render(request, template, context)
    with open(f_curr_sim_code) as json_file:
      sim_code = json.load(json_file)["sim_code"]

  if check_if_file_exists(f_curr_step):
    with open(f_curr_step) as json_file:
      step = json.load(json_file)["step"]
    os.remove(f_curr_step)
  else:
    # Late join: find the latest completed movement step.
    move_files = find_filenames(f"storage/{sim_code}/movement", ".json")
    nums = [int(f.split("/")[-1].split(".")[0]) for f in move_files
            if f.split("/")[-1][0] != "."]
    step = max(nums) if nums else 0

  meta_file = f"storage/{sim_code}/reverie/meta.json"
  sec_per_step = 10
  if check_if_file_exists(meta_file):
    with open(meta_file) as json_file:
      sec_per_step = json.load(json_file).get("sec_per_step", 10)

  persona_names = []
  persona_names_set = set()
  for i in find_filenames(f"storage/{sim_code}/personas", ""):
    x = i.split("/")[-1].strip()
    if x[0] != ".":
      persona_names += [[x, x.replace(" ", "_")]]
      persona_names_set.add(x)

  persona_init_pos = []
  file_count = []
  for i in find_filenames(f"storage/{sim_code}/environment", ".json"):
    x = i.split("/")[-1].strip()
    if x[0] != ".":
      file_count += [int(x.split(".")[0])]
  curr_json = f'storage/{sim_code}/environment/{str(max(file_count))}.json'
  with open(curr_json) as json_file:
    persona_init_pos_dict = json.load(json_file)
    for key, val in persona_init_pos_dict.items():
      if key in persona_names_set:
        persona_init_pos += [[key, val["x"], val["y"]]]

  # Pre-load movement data so the JS execute_movement is never undefined,
  # whether the user loads early or joins mid-run.
  init_movement = "null"
  move_path = f"storage/{sim_code}/movement/{step}.json"
  if check_if_file_exists(move_path):
    with open(move_path) as json_file:
      mv = json.load(json_file)
      mv["<step>"] = step
      init_movement = json.dumps(mv)

  # sec_per_step drives the frontend animation mode: at large step sizes
  # (>= 3600s) the tween engine teleports instead of walking the full path.
  meta_file = f"storage/{sim_code}/reverie/meta.json"
  sec_per_step = 10
  if check_if_file_exists(meta_file):
    with open(meta_file) as json_file:
      sec_per_step = json.load(json_file).get("sec_per_step", 10)

  context = {"sim_code": sim_code,
             "step": step,
             "persona_names": persona_names,
             "persona_init_pos": persona_init_pos,
             "init_movement": init_movement,
             "sec_per_step": sec_per_step,
             "mode": "simulate"}
  template = "home/home.html"
  return render(request, template, context)


def replay(request, sim_code, step): 
  sim_code = sim_code
  step = int(step)

  persona_names = []
  persona_names_set = set()
  for i in find_filenames(f"storage/{sim_code}/personas", ""): 
    x = i.split("/")[-1].strip()
    if x[0] != ".": 
      persona_names += [[x, x.replace(" ", "_")]]
      persona_names_set.add(x)

  persona_init_pos = []
  file_count = []
  for i in find_filenames(f"storage/{sim_code}/environment", ".json"):
    x = i.split("/")[-1].strip()
    if x[0] != ".": 
      file_count += [int(x.split(".")[0])]
  curr_json = f'storage/{sim_code}/environment/{str(max(file_count))}.json'
  with open(curr_json) as json_file:  
    persona_init_pos_dict = json.load(json_file)
    for key, val in persona_init_pos_dict.items(): 
      if key in persona_names_set: 
        persona_init_pos += [[key, val["x"], val["y"]]]

  init_movement = "null"
  move_path = f"storage/{sim_code}/movement/{step}.json"
  if check_if_file_exists(move_path):
    with open(move_path) as json_file:
      mv = json.load(json_file)
      mv["<step>"] = step
      init_movement = json.dumps(mv)

  meta_file = f"storage/{sim_code}/reverie/meta.json"
  sec_per_step = 10
  if check_if_file_exists(meta_file):
    with open(meta_file) as json_file:
      sec_per_step = json.load(json_file).get("sec_per_step", 10)

  context = {"sim_code": sim_code,
             "step": step,
             "persona_names": persona_names,
             "persona_init_pos": persona_init_pos,
             "init_movement": init_movement,
             "sec_per_step": sec_per_step,
             "mode": "replay"}
  template = "home/home.html"
  return render(request, template, context)


def _load_persona_state(sim_code, persona_name):
  """Load a persona's memory state (scratch / spatial / associative memory).

  Shared by the standalone persona_state page and the AJAX
  persona_state_json endpoint used by the in-map side panel.

  ARGS:
    sim_code: simulation code
    persona_name: underscore-joined persona name (e.g. "Abigail_Cruz")
  RETURNS:
    dict with persona_name, persona_name_underscore, scratch, spatial,
    and the event / chat / thought associative-memory lists (newest first).
  """
  persona_name_underscore = persona_name
  persona_name = " ".join(persona_name.split("_"))
  memory = f"storage/{sim_code}/personas/{persona_name}/bootstrap_memory"
  if not os.path.exists(memory):
    memory = f"compressed_storage/{sim_code}/personas/{persona_name}/bootstrap_memory"

  with open(memory + "/scratch.json") as json_file:
    scratch = json.load(json_file)

  with open(memory + "/spatial_memory.json") as json_file:
    spatial = json.load(json_file)

  with open(memory + "/associative_memory/nodes.json") as json_file:
    associative = json.load(json_file)

  a_mem_event = []
  a_mem_chat = []
  a_mem_thought = []

  for count in range(len(associative.keys()), 0, -1):
    node_id = f"node_{str(count)}"
    node_details = associative[node_id]

    if node_details["type"] == "event":
      a_mem_event += [node_details]

    elif node_details["type"] == "chat":
      a_mem_chat += [node_details]

    elif node_details["type"] == "thought":
      a_mem_thought += [node_details]

  return {"persona_name": persona_name,
          "persona_name_underscore": persona_name_underscore,
          "scratch": scratch,
          "spatial": spatial,
          "a_mem_event": a_mem_event,
          "a_mem_chat": a_mem_chat,
          "a_mem_thought": a_mem_thought}


def replay_persona_state(request, sim_code, step, persona_name):
  step = int(step)
  state = _load_persona_state(sim_code, persona_name)

  context = {"sim_code": sim_code,
             "step": step,
             **state}
  template = "persona_state/persona_state.html"
  return render(request, template, context)


def persona_state_json(request, sim_code, persona_name):
  """<BACKEND to FRONTEND> JSON variant of persona state for the in-map side
  panel. Returns the same memory payload as replay_persona_state without a
  page render so the panel can expand State Details inline. The standalone
  view's <step> arg is unused for memory loading, so it is omitted here.
  """
  state = _load_persona_state(sim_code, persona_name)
  return JsonResponse(state)


def path_tester(request):
  context = {}
  template = "path_tester/path_tester.html"
  return render(request, template, context)


def process_environment(request): 
  """
  <FRONTEND to BACKEND> 
  This sends the frontend visual world information to the backend server. 
  It does this by writing the current environment representation to 
  "storage/environment.json" file. 

  ARGS:
    request: Django request
  RETURNS: 
    HttpResponse: string confirmation message. 
  """
  # f_curr_sim_code = "temp_storage/curr_sim_code.json"
  # with open(f_curr_sim_code) as json_file:  
  #   sim_code = json.load(json_file)["sim_code"]

  data = json.loads(request.body)
  step = data["step"]
  sim_code = data["sim_code"]
  environment = data["environment"]

  with open(f"storage/{sim_code}/environment/{step}.json", "w") as outfile:
    outfile.write(json.dumps(environment, indent=2))

  return HttpResponse("received")


def update_environment(request): 
  """
  <BACKEND to FRONTEND> 
  This sends the backend computation of the persona behavior to the frontend
  visual server. 
  It does this by reading the new movement information from 
  "storage/movement.json" file.

  ARGS:
    request: Django request
  RETURNS: 
    HttpResponse
  """
  # f_curr_sim_code = "temp_storage/curr_sim_code.json"
  # with open(f_curr_sim_code) as json_file:  
  #   sim_code = json.load(json_file)["sim_code"]

  data = json.loads(request.body)
  step = data["step"]
  sim_code = data["sim_code"]

  response_data = {"<step>": -1}
  if (check_if_file_exists(f"storage/{sim_code}/movement/{step}.json")):
    with open(f"storage/{sim_code}/movement/{step}.json") as json_file: 
      response_data = json.load(json_file)
      response_data["<step>"] = step

  return JsonResponse(response_data)


def path_tester_update(request): 
  """
  Processing the path and saving it to path_tester_env.json temp storage for 
  conducting the path tester. 

  ARGS:
    request: Django request
  RETURNS: 
    HttpResponse: string confirmation message. 
  """
  data = json.loads(request.body)
  camera = data["camera"]

  with open(f"temp_storage/path_tester_env.json", "w") as outfile:
    outfile.write(json.dumps(camera, indent=2))

  return HttpResponse("received")









