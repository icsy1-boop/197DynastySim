"""
Author: Joon Sung Park (joonspk@stanford.edu)

File: reverie.py
Description: This is the main program for running generative agent simulations
that defines the ReverieServer class. This class maintains and records all  
states related to the simulation. The primary mode of interaction for those  
running the simulation should be through the open_server function, which  
enables the simulator to input command-line prompts for running and saving  
the simulation, among other tasks.

Release note (June 14, 2023) -- Reverie implements the core simulation 
mechanism described in my paper entitled "Generative Agents: Interactive 
Simulacra of Human Behavior." If you are reading through these lines after 
having read the paper, you might notice that I use older terms to describe 
generative agents and their cognitive modules here. Most notably, I use the 
term "personas" to refer to generative agents, "associative memory" to refer 
to the memory stream, and "reverie" to refer to the overarching simulation 
framework.
"""
import json
import csv
import numpy
import datetime
import pickle
import time
import math
import os
import shutil
import traceback
import signal
import random
import faulthandler
from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED
from persona.prompt_template.gpt_structure import set_persona_tier

faulthandler.enable()
faulthandler.register(signal.SIGUSR1, all_threads=True, chain=False)

from selenium import webdriver

from global_methods import *
from utils import *
from maze import *
from persona.persona import *
from barangay_mechanics import (inject_dynasty_memories, log_corruption_step,
                                load_agent_rows, load_world_metrics, save_world_metrics)
from barangay_election import (run_election, poll_political_intentions,
                               announce_election, finalize_candidacy)
from barangay_news import broadcast_news
from barangay_corruption_events import step_corruption_events
from barangay_unrest import step_unrest
from barangay_survey import conduct_survey

# Path to the barangay agents CSV that this sim was bootstrapped from. MUST match
# the running population or corruption/election/news see the wrong agents. Set via
# the BARANGAY_CSV env var per sim (control -> dynasty CSV, treatment -> anti-dynasty CSV).
_BARANGAY_CSV = os.environ.get("BARANGAY_CSV") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../barangay_agents_qc_1000_final-1.csv"))

# Election fires at this step (month 4 at 1hr/step = 2880; override via ELECTION_STEP env var)
_ELECTION_STEP = int(os.environ.get("ELECTION_STEP", 2880))
# Set ANTIDYNASTY=1 to enforce no-family-in-office constraint during election
_ANTIDYNASTY = os.environ.get("ANTIDYNASTY", "0") == "1"
# Interval constants (env-overridable so the election campaign can be compressed
# for short test runs, e.g. ELECTION_MONTH=168 ELECTION_WEEK=48 ELECTION_STEP=336).
_MONTH = int(os.environ.get("ELECTION_MONTH", 720))   # announce lead / poll cadence
_WEEK  = int(os.environ.get("ELECTION_WEEK", 168))    # weekly cadence (news/candidacy/survey)
_CORRUPTION_INTERVAL = int(os.environ.get("CORRUPTION_INTERVAL", 48))  # ~2 sim-days
_PROTEST_INTERVAL = int(os.environ.get("PROTEST_INTERVAL", 72))        # ~3 sim-days
# Output directory for corruption logs and CSV exports
_BARANGAY_OUTPUT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../output/barangay"))

##############################################################################
#                                  REVERIE                                   #
##############################################################################

class ReverieServer: 
  def __init__(self, 
               fork_sim_code,
               sim_code):
    # FORKING FROM A PRIOR SIMULATION:
    # <fork_sim_code> indicates the simulation we are forking from. 
    # Interestingly, all simulations must be forked from some initial 
    # simulation, where the first simulation is "hand-crafted".
    self.fork_sim_code = fork_sim_code
    fork_folder = f"{fs_storage}/{self.fork_sim_code}"

    # <sim_code> indicates our current simulation. The first step here is to 
    # copy everything that's in <fork_sim_code>, but edit its 
    # reverie/meta/json's fork variable. 
    self.sim_code = sim_code
    sim_folder = f"{fs_storage}/{self.sim_code}"

    # If the target folder already exists, resume in-place instead of
    # overwriting it with a fresh copy from the fork source.
    resuming = os.path.exists(sim_folder)
    if not resuming:
      copyanything(fork_folder, sim_folder)


    with open(f"{sim_folder}/reverie/meta.json") as json_file:
      reverie_meta = json.load(json_file)

    if not resuming:
      with open(f"{sim_folder}/reverie/meta.json", "w") as outfile:
        reverie_meta["fork_sim_code"] = fork_sim_code
        outfile.write(json.dumps(reverie_meta, indent=2))

    if resuming:
      print(f"Resuming existing simulation '{sim_code}' at step {reverie_meta['step']}.")

    # LOADING REVERIE'S GLOBAL VARIABLES
    # The start datetime of the Reverie: 
    # <start_datetime> is the datetime instance for the start datetime of 
    # the Reverie instance. Once it is set, this is not really meant to 
    # change. It takes a string date in the following example form: 
    # "June 25, 2022"
    # e.g., ...strptime(June 25, 2022, "%B %d, %Y")
    self.start_time = datetime.datetime.strptime(
                        f"{reverie_meta['start_date']}, 00:00:00",  
                        "%B %d, %Y, %H:%M:%S")
    # <curr_time> is the datetime instance that indicates the game's current
    # time. This gets incremented by <sec_per_step> amount everytime the world
    # progresses (that is, everytime curr_env_file is recieved). 
    self.curr_time = datetime.datetime.strptime(reverie_meta['curr_time'], 
                                                "%B %d, %Y, %H:%M:%S")
    # <sec_per_step> denotes the number of seconds in game time that each 
    # step moves foward. 
    self.sec_per_step = reverie_meta['sec_per_step']
    
    # <maze> is the main Maze instance. Note that we pass in the maze_name
    # (e.g., "double_studio") to instantiate Maze. 
    # e.g., Maze("double_studio")
    self.maze = Maze(reverie_meta['maze_name'])
    
    # <step> denotes the number of steps that our game has taken. A step here
    # literally translates to the number of moves our personas made in terms
    # of the number of tiles. 
    self.step = reverie_meta['step']

    # SETTING UP PERSONAS IN REVERIE
    # <personas> is a dictionary that takes the persona's full name as its 
    # keys, and the actual persona instance as its values.
    # This dictionary is meant to keep track of all personas who are part of
    # the Reverie instance. 
    # e.g., ["Isabella Rodriguez"] = Persona("Isabella Rodriguezs")
    self.personas = dict()
    # <personas_tile> is a dictionary that contains the tile location of
    # the personas (!-> NOT px tile, but the actual tile coordinate).
    # The tile take the form of a set, (row, col). 
    # e.g., ["Isabella Rodriguez"] = (58, 39)
    self.personas_tile = dict()
    
    # # <persona_convo_match> is a dictionary that describes which of the two
    # # personas are talking to each other. It takes a key of a persona's full
    # # name, and value of another persona's full name who is talking to the 
    # # original persona. 
    # # e.g., dict["Isabella Rodriguez"] = ["Maria Lopez"]
    # self.persona_convo_match = dict()
    # # <persona_convo> contains the actual content of the conversations. It
    # # takes as keys, a pair of persona names, and val of a string convo. 
    # # Note that the key pairs are *ordered alphabetically*. 
    # # e.g., dict[("Adam Abraham", "Zane Xu")] = "Adam: baba \n Zane:..."
    # self.persona_convo = dict()

    # Loading in all personas. 
    init_env_file = f"{sim_folder}/environment/{str(self.step)}.json"
    init_env = json.load(open(init_env_file))
    for persona_name in reverie_meta['persona_names']: 
      persona_folder = f"{sim_folder}/personas/{persona_name}"
      p_x = init_env[persona_name]["x"]
      p_y = init_env[persona_name]["y"]
      curr_persona = Persona(persona_name, persona_folder)

      self.personas[persona_name] = curr_persona
      self.personas_tile[persona_name] = (p_x, p_y)
      self.maze.tiles[p_y][p_x]["events"].add(curr_persona.scratch
                                              .get_curr_event_and_desc())

    # BARANGAY: Load agent rows for corruption tracking and inject dynasty bonds.
    # barangay_agent_rows: dict {name: row} used by log_corruption_step
    # barangay_agent_list: list of rows used by election/news functions
    self.barangay_agent_rows = load_agent_rows(_BARANGAY_CSV)
    self.barangay_agent_list = list(self.barangay_agent_rows.values())
    if self.barangay_agent_rows:
      inject_dynasty_memories(self.personas, _BARANGAY_CSV)

    # REVERIE SETTINGS PARAMETERS:
    # <server_sleep> denotes the amount of time that our while loop rests each
    # cycle; this is to not kill our machine.
    self.server_sleep = 0.1
    # {name -> position_key} — populated by monthly/weekly polls, used at election
    self._declared_candidates = {}
    # World metrics (corruption/welfare/unrest) persist per-sim so the integrated
    # welfare/unrest state accumulates across autosaves and VM reboots instead of
    # resetting every restart.
    self._metrics_dir = f"{sim_folder}/reverie"
    self._world_metrics = load_world_metrics(self._metrics_dir)
    # persistent corruption from active corruption events; restored from disk.
    self._corruption_event_bonus = float(self._world_metrics.get("event_bonus", 0.0))

    # SIGNALING THE FRONTEND SERVER: 
    # curr_sim_code.json contains the current simulation code, and
    # curr_step.json contains the current step of the simulation. These are 
    # used to communicate the code and step information to the frontend. 
    # Note that step file is removed as soon as the frontend opens up the 
    # simulation. 
    curr_sim_code = dict()
    curr_sim_code["sim_code"] = self.sim_code
    with open(f"{fs_temp_storage}/curr_sim_code.json", "w") as outfile: 
      outfile.write(json.dumps(curr_sim_code, indent=2))
    
    curr_step = dict()
    curr_step["step"] = self.step
    with open(f"{fs_temp_storage}/curr_step.json", "w") as outfile: 
      outfile.write(json.dumps(curr_step, indent=2))


  def save(self): 
    """
    Save all Reverie progress -- this includes Reverie's global state as well
    as all the personas.  

    INPUT
      None
    OUTPUT 
      None
      * Saves all relevant data to the designated memory directory
    """
    # <sim_folder> points to the current simulation folder.
    sim_folder = f"{fs_storage}/{self.sim_code}"

    # Save Reverie meta information.
    reverie_meta = dict() 
    reverie_meta["fork_sim_code"] = self.fork_sim_code
    reverie_meta["start_date"] = self.start_time.strftime("%B %d, %Y")
    reverie_meta["curr_time"] = self.curr_time.strftime("%B %d, %Y, %H:%M:%S")
    reverie_meta["sec_per_step"] = self.sec_per_step
    reverie_meta["maze_name"] = self.maze.maze_name
    reverie_meta["persona_names"] = list(self.personas.keys())
    reverie_meta["step"] = self.step
    reverie_meta_f = f"{sim_folder}/reverie/meta.json"
    with open(reverie_meta_f, "w") as outfile:
      outfile.write(json.dumps(reverie_meta, indent=2))

    # Persist integrated world metrics (welfare/unrest/corruption/event_bonus)
    # per-sim so the feedback loop accumulates across reboots.
    self._world_metrics["event_bonus"] = self._corruption_event_bonus
    save_world_metrics(self._metrics_dir, self._world_metrics)

    # Save the personas.
    for persona_name, persona in self.personas.items(): 
      save_folder = f"{sim_folder}/personas/{persona_name}/bootstrap_memory"
      persona.save(save_folder)


  def start_path_tester_server(self): 
    """
    Starts the path tester server. This is for generating the spatial memory
    that we need for bootstrapping a persona's state. 

    To use this, you need to open server and enter the path tester mode, and
    open the front-end side of the browser. 

    INPUT 
      None
    OUTPUT 
      None
      * Saves the spatial memory of the test agent to the path_tester_env.json
        of the temp storage. 
    """
    def print_tree(tree): 
      def _print_tree(tree, depth):
        dash = " >" * depth

        if type(tree) == type(list()): 
          if tree:
            print (dash, tree)
          return 

        for key, val in tree.items(): 
          if key: 
            print (dash, key)
          _print_tree(val, depth+1)
      
      _print_tree(tree, 0)

    # <curr_vision> is the vision radius of the test agent. Recommend 8 as 
    # our default. 
    curr_vision = 8
    # <s_mem> is our test spatial memory. 
    s_mem = dict()

    # The main while loop for the test agent. 
    while (True): 
      try: 
        curr_dict = {}
        tester_file = fs_temp_storage + "/path_tester_env.json"
        if check_if_file_exists(tester_file): 
          with open(tester_file) as json_file: 
            curr_dict = json.load(json_file)
            os.remove(tester_file)
          
          # Current camera location
          curr_sts = self.maze.sq_tile_size
          curr_camera = (int(math.ceil(curr_dict["x"]/curr_sts)), 
                         int(math.ceil(curr_dict["y"]/curr_sts))+1)
          curr_tile_det = self.maze.access_tile(curr_camera)

          # Initiating the s_mem
          world = curr_tile_det["world"]
          if curr_tile_det["world"] not in s_mem: 
            s_mem[world] = dict()

          # Iterating throughn the nearby tiles.
          nearby_tiles = self.maze.get_nearby_tiles(curr_camera, curr_vision)
          for i in nearby_tiles: 
            i_det = self.maze.access_tile(i)
            if (curr_tile_det["sector"] == i_det["sector"] 
                and curr_tile_det["arena"] == i_det["arena"]): 
              if i_det["sector"] != "": 
                if i_det["sector"] not in s_mem[world]: 
                  s_mem[world][i_det["sector"]] = dict()
              if i_det["arena"] != "": 
                if i_det["arena"] not in s_mem[world][i_det["sector"]]: 
                  s_mem[world][i_det["sector"]][i_det["arena"]] = list()
              if i_det["game_object"] != "": 
                if (i_det["game_object"] 
                    not in s_mem[world][i_det["sector"]][i_det["arena"]]):
                  s_mem[world][i_det["sector"]][i_det["arena"]] += [
                                                         i_det["game_object"]]

        # Incrementally outputting the s_mem and saving the json file. 
        print ("= " * 15)
        out_file = fs_temp_storage + "/path_tester_out.json"
        with open(out_file, "w") as outfile: 
          outfile.write(json.dumps(s_mem, indent=2))
        print_tree(s_mem)

      except:
        pass

      time.sleep(self.server_sleep * 10)


  def start_server(self, int_counter): 
    """
    The main backend server of Reverie. 
    This function retrieves the environment file from the frontend to 
    understand the state of the world, calls on each personas to make 
    decisions based on the world state, and saves their moves at certain step
    intervals. 
    INPUT
      int_counter: Integer value for the number of steps left for us to take
                   in this iteration. 
    OUTPUT 
      None
    """
    # <sim_folder> points to the current simulation folder.
    sim_folder = f"{fs_storage}/{self.sim_code}"

    # When a persona arrives at a game object, we give a unique event
    # to that object.
    # e.g., ('double studio[...]:bed', 'is', 'unmade', 'unmade')
    # Later on, before this cycle ends, we need to return that to its
    # initial state, like this:
    # e.g., ('double studio[...]:bed', None, None, None)
    # So we need to keep track of which event we added.
    # <game_obj_cleanup> is used for that.
    game_obj_cleanup = dict()

    # Step logger: one CSV row per completed step.
    os.makedirs(_BARANGAY_OUTPUT, exist_ok=True)
    _step_log_path = os.path.join(_BARANGAY_OUTPUT, "sim_log.csv")
    _log_header_needed = not os.path.exists(_step_log_path)
    _step_log_file = open(_step_log_path, "a", newline="")
    _step_log_writer = csv.writer(_step_log_file)
    if _log_header_needed:
      _step_log_writer.writerow(
        ["step", "sim_time", "wall_elapsed_s", "n_agents", "n_tier1", "n_tier2"])
    _n_tier1 = sum(1 for p in self.personas.values()
                   if getattr(p.scratch, 'agent_tier', 1) == 1)
    _n_tier2 = len(self.personas) - _n_tier1

    # The main while loop of Reverie.
    while (True): 
      # Done with this iteration if <int_counter> reaches 0. 
      if int_counter == 0: 
        break

      # <curr_env_file> file is the file that our frontend outputs. When the
      # frontend has done its job and moved the personas, then it will put a 
      # new environment file that matches our step count. That's when we run 
      # the content of this for loop. Otherwise, we just wait. 
      curr_env_file = f"{sim_folder}/environment/{self.step}.json"
      if check_if_file_exists(curr_env_file):
        # If we have an environment file, it means we have a new perception
        # input to our personas. So we first retrieve it.
        try: 
          # Try and save block for robustness of the while loop.
          with open(curr_env_file) as json_file:
            new_env = json.load(json_file)
            env_retrieved = True
        except: 
          pass
      
        if env_retrieved:
          _step_wall_start = time.time()
          # This is where we go through <game_obj_cleanup> to clean up all
          # object actions that were used in this cylce. 
          for key, val in game_obj_cleanup.items(): 
            # We turn all object actions to their blank form (with None). 
            self.maze.turn_event_from_tile_idle(key, val)
          # Then we initialize game_obj_cleanup for this cycle. 
          game_obj_cleanup = dict()

          # We first move our personas in the backend environment to match 
          # the frontend environment. 
          for persona_name, persona in self.personas.items(): 
            # <curr_tile> is the tile that the persona was at previously. 
            curr_tile = self.personas_tile[persona_name]
            # <new_tile> is the tile that the persona will move to right now,
            # during this cycle. Fall back to current tile for agents that
            # timed out and weren't included in the environment file.
            if persona_name in new_env:
              new_tile = (new_env[persona_name]["x"],
                          new_env[persona_name]["y"])
            else:
              new_tile = curr_tile

            # We actually move the persona on the backend tile map here. 
            self.personas_tile[persona_name] = new_tile
            self.maze.remove_subject_events_from_tile(persona.name, curr_tile)
            self.maze.add_event_from_tile(persona.scratch
                                         .get_curr_event_and_desc(), new_tile)

            # Now, the persona will travel to get to their destination. *Once*
            # the persona gets there, we activate the object action.
            if not persona.scratch.planned_path: 
              # We add that new object action event to the backend tile map. 
              # At its creation, it is stored in the persona's backend. 
              game_obj_cleanup[persona.scratch
                               .get_curr_obj_event_and_desc()] = new_tile
              self.maze.add_event_from_tile(persona.scratch
                                     .get_curr_obj_event_and_desc(), new_tile)
              # We also need to remove the temporary blank action for the 
              # object that is currently taking the action. 
              blank = (persona.scratch.get_curr_obj_event_and_desc()[0], 
                       None, None, None)
              self.maze.remove_event_from_tile(blank, new_tile)

          # Then we need to actually have each of the personas perceive and
          # move. The movement for each of the personas comes in the form of
          # x y coordinates where the persona will move towards. e.g., (50, 34)
          # Persona moves run in parallel: each persona.move() is dominated by
          # LLM HTTP latency, so threads are an effective concurrency primitive.
          movements = {"persona": dict(), "meta": dict()}

          def _run_persona_move(item):
            persona_name, persona = item
            set_persona_tier(getattr(persona.scratch, 'agent_tier', 2))
            next_tile, pronunciatio, description, path = persona.move(
              self.maze, self.personas, self.personas_tile[persona_name],
              self.curr_time)
            return persona_name, persona, next_tile, pronunciatio, description, path

          _step_start = time.time()
          results = []
          _executor = ThreadPoolExecutor(
              max_workers=int(os.environ.get("MOVE_MAX_WORKERS", 150)))
          fut_map = {_executor.submit(_run_persona_move, item): item[0]
                     for item in self.personas.items()}
          deadline = time.time() + 3600
          pending = set(fut_map.keys())
          while pending and time.time() < deadline:
            remaining = deadline - time.time()
            done_batch, pending = wait(
              pending, timeout=min(10.0, remaining),
              return_when=FIRST_COMPLETED)
            for fut in done_batch:
              name = fut_map[fut]
              try:
                results.append(fut.result())
              except Exception as e:
                print(f"[SKIP] {name}: {e}", flush=True)
          for fut in pending:
            name = fut_map[fut]
            print(f"[SKIP] {name} timed out after 3600s", flush=True)
          _executor.shutdown(wait=False)
          elapsed = time.time() - _step_start
          print(f"[STEP {self.step} DONE] elapsed={elapsed:.1f}s agents={len(results)}/{len(self.personas)} wall-time={datetime.datetime.now().strftime('%H:%M:%S')}", flush=True)

          for persona_name, persona, next_tile, pronunciatio, description, path in results:
            if next_tile is None or path is None:
              continue
            movements["persona"][persona_name] = {}
            movements["persona"][persona_name]["movement"] = next_tile
            movements["persona"][persona_name]["path"] = [list(t) for t in path]
            movements["persona"][persona_name]["pronunciatio"] = pronunciatio
            movements["persona"][persona_name]["description"] = description
            movements["persona"][persona_name]["chat"] = persona.scratch.chat

          # Include the meta information about the current stage in the 
          # movements dictionary. 
          movements["meta"]["curr_time"] = (self.curr_time 
                                             .strftime("%B %d, %Y, %H:%M:%S"))

          # We then write the personas' movements to a file that will be sent 
          # to the frontend server. 
          # Example json output: 
          # {"persona": {"Maria Lopez": {"movement": [58, 9]}},
          #  "persona": {"Klaus Mueller": {"movement": [38, 12]}}, 
          #  "meta": {curr_time: <datetime>}}
          curr_move_file = f"{sim_folder}/movement/{self.step}.json"
          os.makedirs(f"{sim_folder}/movement", exist_ok=True)
          with open(curr_move_file, "w") as outfile:
            outfile.write(json.dumps(movements, indent=2))

          # After this cycle, the world takes one step forward, and the
          # current time moves by <sec_per_step> amount.
          self.step += 1
          self.curr_time += datetime.timedelta(seconds=self.sec_per_step)

          _step_log_writer.writerow([
            self.step,
            self.curr_time.strftime("%Y-%m-%d %H:%M:%S"),
            round(time.time() - _step_wall_start, 2),
            len(self.personas),
            _n_tier1,
            _n_tier2,
          ])
          _step_log_file.flush()

          # BARANGAY: log corruption metric every 10 steps; keep latest for news broadcasts.
          # Returns {corruption_index, welfare_score, unrest, dynasty_bonus}; the trait
          # baseline is combined with the persistent event bonus so witnessed corruption
          # accumulates instead of being recomputed away.
          if self.step % 10 == 0 and self.barangay_agent_rows:
            self._world_metrics = log_corruption_step(
                self.personas, self.barangay_agent_rows,
                self.step, self.curr_time, self._metrics_dir,
                event_bonus=self._corruption_event_bonus,
                prev_metrics=self._world_metrics)

          int_counter -= 1

          # Autosave every 24 steps (one sim-day) to survive VM reboots.
          if self.step % 24 == 0:
            self.save()

          # Weekly news broadcast — one LLM call, injected into media-connected agents.
          # Information spreads to others organically through conversations.
          if self.step > 0 and self.step % _WEEK == 0 and self.barangay_agent_rows:
            world_metrics = getattr(self, "_world_metrics", {})
            # Add election context note when election is approaching
            context_notes = ""
            steps_to_election = _ELECTION_STEP - self.step
            if 0 < steps_to_election <= _MONTH:
              election_date = (self.curr_time +
                               datetime.timedelta(hours=steps_to_election)
                              ).strftime("%B %d, %Y")
              context_notes = (f"The local government election is coming on "
                               f"{election_date}.")
            broadcast_news(self.personas, self.barangay_agent_list,
                           world_metrics, self.curr_time, context_notes)

          # Active corruption events — greedy officials may act corruptly; the
          # population hears about it (memory -> election), and it raises the
          # world corruption index that the news bulletin reflects.
          if (self.step > 0 and self.step % _CORRUPTION_INTERVAL == 0
              and self.barangay_agent_rows):
            try:
              _n, _exp, _d = step_corruption_events(
                  self.personas, self.barangay_agent_list, self.curr_time)
              if _d:
                # Accumulate persistently (capped) so the next 10-step recompute
                # folds it into the baseline rather than discarding it.
                self._corruption_event_bonus = min(
                    0.5, self._corruption_event_bonus + _d)
                self._world_metrics["event_bonus"] = self._corruption_event_bonus
                _cur = self._world_metrics.get("corruption_index", 0.5)
                self._world_metrics["corruption_index"] = min(1.0, _cur + _d)
            except Exception as _e:
              print(f"[CORRUPTION] tick failed: {_e}", flush=True)

          # Unrest-driven protests — when integrated unrest is high, residents
          # protest: anti-incumbent memories (-> votes) + a news flash. Closes
          # corruption -> welfare down -> unrest up -> protest -> election.
          if (self.step > 0 and self.step % _PROTEST_INTERVAL == 0
              and self.barangay_agent_rows):
            try:
              _pn, _ptext = step_unrest(
                  self.personas, self.barangay_agent_list,
                  self._world_metrics, self.curr_time)
              if _ptext:
                _ev = self._world_metrics.setdefault("recent_events", [])
                _ev.append(_ptext)
                self._world_metrics["recent_events"] = _ev[-3:]
            except Exception as _e:
              print(f"[PROTEST] tick failed: {_e}", flush=True)

          # ── Election timeline ──────────────────────────────────────────────
          if self.barangay_agent_rows:
            _eday = _ELECTION_STEP
            _announce = _eday - _MONTH       # 1 month before
            _final_cand = _eday - 72         # 3 days before (lock-in)

            # Pre-announcement: monthly intention polls
            # Fires every _MONTH steps before the announcement.
            if (0 < self.step < _announce and self.step % _MONTH == 0):
              print(f"[ELECTION] Monthly political intention poll at step {self.step}")
              self._declared_candidates = poll_political_intentions(
                  self.personas, self._declared_candidates,
                  self.barangay_agent_list, self.curr_time,
                  announced=False)

            # Announcement: 1 month before election
            elif self.step == _announce:
              _election_date_str = (
                  self.curr_time + datetime.timedelta(hours=_MONTH)
              ).strftime("%B %d, %Y")
              announce_election(self.personas, self.barangay_agent_list,
                                _election_date_str, self.curr_time)
              # Also poll immediately after announcement
              self._declared_candidates = poll_political_intentions(
                  self.personas, self._declared_candidates,
                  self.barangay_agent_list, self.curr_time,
                  announced=True, election_date_str=_election_date_str)

            # Post-announcement: weekly re-checks until lock-in
            elif (_announce < self.step < _final_cand and
                  (self.step - _announce) % _WEEK == 0):
              _election_date_str = (
                  self.curr_time + datetime.timedelta(
                      hours=_eday - self.step)
              ).strftime("%B %d, %Y")
              print(f"[ELECTION] Weekly candidacy check at step {self.step}")
              self._declared_candidates = poll_political_intentions(
                  self.personas, self._declared_candidates,
                  self.barangay_agent_list, self.curr_time,
                  announced=True, election_date_str=_election_date_str)

            # Lock-in: finalize candidate list 3 days before election
            elif self.step == _final_cand:
              print(f"[ELECTION] Finalizing candidates at step {self.step}")
              self._election_candidates = finalize_candidacy(
                  self._declared_candidates)

            # Election day
            elif self.step == _eday:
              print(f"[ELECTION] Voting at step {self.step} "
                    f"(antidynasty={_ANTIDYNASTY})")
              winners = run_election(
                  self.personas, self.barangay_agent_list,
                  antidynasty=_ANTIDYNASTY,
                  curr_time=self.curr_time,
                  candidates=getattr(self, "_election_candidates", None),
              )
              print(f"[ELECTION] Winners: {winners}")
              self.save()

            # Journalist election survey — weekly opinion poll from the
            # announcement up to election day (once >=2 candidates exist for a
            # headline race). Journalists interview a sample of residents; the
            # published poll is injected as memories + news, informing voters and
            # enabling bandwagon/strategic shifts in the real vote.
            if (_announce < self.step < _eday and
                (self.step - _announce) % _WEEK == 0):
              try:
                _stext = conduct_survey(
                    self.personas, self.barangay_agent_list,
                    self._declared_candidates, self.curr_time)
                if _stext:
                  _ev = self._world_metrics.setdefault("recent_events", [])
                  _ev.append(_stext)
                  self._world_metrics["recent_events"] = _ev[-3:]
              except Exception as _e:
                print(f"[SURVEY] tick failed: {_e}", flush=True)

      # Sleep so we don't burn our machines.
      time.sleep(self.server_sleep)


  def open_server(self): 
    """
    Open up an interactive terminal prompt that lets you run the simulation 
    step by step and probe agent state. 

    INPUT 
      None
    OUTPUT
      None
    """
    print ("Note: The agents in this simulation package are computational")
    print ("constructs powered by generative agents architecture and LLM. We")
    print ("clarify that these agents lack human-like agency, consciousness,")
    print ("and independent decision-making.\n---")

    # <sim_folder> points to the current simulation folder.
    sim_folder = f"{fs_storage}/{self.sim_code}"

    while True: 
      sim_command = input("Enter option: ")
      sim_command = sim_command.strip()
      ret_str = ""

      try: 
        if sim_command.lower() in ["f", "fin", "finish", "save and finish"]: 
          # Finishes the simulation environment and saves the progress. 
          # Example: fin
          self.save()
          break

        elif sim_command.lower() == "start path tester mode": 
          # Starts the path tester and removes the currently forked sim files.
          # Note that once you start this mode, you need to exit out of the
          # session and restart in case you want to run something else. 
          shutil.rmtree(sim_folder) 
          self.start_path_tester_server()

        elif sim_command.lower() == "exit": 
          # Finishes the simulation environment but does not save the progress
          # and erases all saved data from current simulation. 
          # Example: exit 
          shutil.rmtree(sim_folder) 
          break 

        elif sim_command.lower() == "save": 
          # Saves the current simulation progress. 
          # Example: save
          self.save()

        elif sim_command[:3].lower() == "run":
          # run 1000          → run 1000 steps from now
          # run until 5000    → run until step 5000 total
          parts = sim_command.split()
          if len(parts) == 3 and parts[1].lower() == "until":
            target_step = int(parts[2])
            if target_step <= self.step:
              print(f"Already at step {self.step}, target {target_step} already reached.")
            else:
              rs.start_server(target_step - self.step)
          else:
            int_count = int(parts[-1])
            rs.start_server(int_count)

        elif ("print persona schedule" 
              in sim_command[:22].lower()): 
          # Print the decomposed schedule of the persona specified in the 
          # prompt.
          # Example: print persona schedule Isabella Rodriguez
          ret_str += (self.personas[" ".join(sim_command.split()[-2:])]
                      .scratch.get_str_daily_schedule_summary())

        elif ("print all persona schedule" 
              in sim_command[:26].lower()): 
          # Print the decomposed schedule of all personas in the world. 
          # Example: print all persona schedule
          for persona_name, persona in self.personas.items(): 
            ret_str += f"{persona_name}\n"
            ret_str += f"{persona.scratch.get_str_daily_schedule_summary()}\n"
            ret_str += f"---\n"

        elif ("print hourly org persona schedule" 
              in sim_command.lower()): 
          # Print the hourly schedule of the persona specified in the prompt.
          # This one shows the original, non-decomposed version of the 
          # schedule.
          # Ex: print persona schedule Isabella Rodriguez
          ret_str += (self.personas[" ".join(sim_command.split()[-2:])]
                      .scratch.get_str_daily_schedule_hourly_org_summary())

        elif ("print persona current tile" 
              in sim_command[:26].lower()): 
          # Print the x y tile coordinate of the persona specified in the 
          # prompt. 
          # Ex: print persona current tile Isabella Rodriguez
          ret_str += str(self.personas[" ".join(sim_command.split()[-2:])]
                      .scratch.curr_tile)

        elif ("print persona chatting with buffer" 
              in sim_command.lower()): 
          # Print the chatting with buffer of the persona specified in the 
          # prompt.
          # Ex: print persona chatting with buffer Isabella Rodriguez
          curr_persona = self.personas[" ".join(sim_command.split()[-2:])]
          for p_n, count in curr_persona.scratch.chatting_with_buffer.items(): 
            ret_str += f"{p_n}: {count}"

        elif ("print persona associative memory (event)" 
              in sim_command.lower()):
          # Print the associative memory (event) of the persona specified in
          # the prompt
          # Ex: print persona associative memory (event) Isabella Rodriguez
          ret_str += f'{self.personas[" ".join(sim_command.split()[-2:])]}\n'
          ret_str += (self.personas[" ".join(sim_command.split()[-2:])]
                                       .a_mem.get_str_seq_events())

        elif ("print persona associative memory (thought)" 
              in sim_command.lower()): 
          # Print the associative memory (thought) of the persona specified in
          # the prompt
          # Ex: print persona associative memory (thought) Isabella Rodriguez
          ret_str += f'{self.personas[" ".join(sim_command.split()[-2:])]}\n'
          ret_str += (self.personas[" ".join(sim_command.split()[-2:])]
                                       .a_mem.get_str_seq_thoughts())

        elif ("print persona associative memory (chat)" 
              in sim_command.lower()): 
          # Print the associative memory (chat) of the persona specified in
          # the prompt
          # Ex: print persona associative memory (chat) Isabella Rodriguez
          ret_str += f'{self.personas[" ".join(sim_command.split()[-2:])]}\n'
          ret_str += (self.personas[" ".join(sim_command.split()[-2:])]
                                       .a_mem.get_str_seq_chats())

        elif ("print persona spatial memory" 
              in sim_command.lower()): 
          # Print the spatial memory of the persona specified in the prompt
          # Ex: print persona spatial memory Isabella Rodriguez
          self.personas[" ".join(sim_command.split()[-2:])].s_mem.print_tree()

        elif ("print current time" 
              in sim_command[:18].lower()): 
          # Print the current time of the world. 
          # Ex: print current time
          ret_str += f'{self.curr_time.strftime("%B %d, %Y, %H:%M:%S")}\n'
          ret_str += f'steps: {self.step}'

        elif ("print tile event" 
              in sim_command[:16].lower()): 
          # Print the tile events in the tile specified in the prompt 
          # Ex: print tile event 50, 30
          cooordinate = [int(i.strip()) for i in sim_command[16:].split(",")]
          for i in self.maze.access_tile(cooordinate)["events"]: 
            ret_str += f"{i}\n"

        elif ("print tile details" 
              in sim_command.lower()): 
          # Print the tile details of the tile specified in the prompt 
          # Ex: print tile event 50, 30
          cooordinate = [int(i.strip()) for i in sim_command[18:].split(",")]
          for key, val in self.maze.access_tile(cooordinate).items(): 
            ret_str += f"{key}: {val}\n"

        elif ("call -- analysis" 
              in sim_command.lower()): 
          # Starts a stateless chat session with the agent. It does not save 
          # anything to the agent's memory. 
          # Ex: call -- analysis Isabella Rodriguez
          persona_name = sim_command[len("call -- analysis"):].strip() 
          self.personas[persona_name].open_convo_session("analysis")

        elif ("call -- load history" 
              in sim_command.lower()): 
          curr_file = maze_assets_loc + "/" + sim_command[len("call -- load history"):].strip() 
          # call -- load history the_ville/agent_history_init_n3.csv

          rows = read_file_to_list(curr_file, header=True, strip_trail=True)[1]
          clean_whispers = []
          for row in rows: 
            agent_name = row[0].strip() 
            whispers = row[1].split(";")
            whispers = [whisper.strip() for whisper in whispers]
            for whisper in whispers: 
              clean_whispers += [[agent_name, whisper]]

          load_history_via_whisper(self.personas, clean_whispers)

        print (ret_str)

      except:
        traceback.print_exc()
        print ("Error.")
        pass


if __name__ == '__main__':
  origin = input("Enter the name of the forked simulation: ").strip()
  target_input = input("Enter the name of the new simulation (or press Enter to resume origin): ").strip()
  target = target_input if target_input else origin

  rs = ReverieServer(origin, target)
  rs.open_server()




















































