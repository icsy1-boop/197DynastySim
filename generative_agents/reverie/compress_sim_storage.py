"""
Author: Joon Sung Park (joonspk@stanford.edu)

File: compress_sim_storage.py
Description: Compresses a simulation for replay demos. 
"""
import shutil
import json
from global_methods import *

def compress(sim_code):
  sim_storage = f"../environment/frontend_server/storage/{sim_code}"
  compressed_storage = f"../environment/frontend_server/compressed_storage/{sim_code}"
  persona_folder = sim_storage + "/personas"
  move_folder = sim_storage + "/movement"
  meta_file = sim_storage + "/reverie/meta.json"

  persona_names = []
  for i in find_filenames(persona_folder, ""): 
    x = i.split("/")[-1].strip()
    if x[0] != ".": 
      persona_names += [x]

  max_move_count = max([int(i.split("/")[-1].split(".")[0]) 
                 for i in find_filenames(move_folder, "json")])
  
  persona_last_move = dict()
  master_move = dict()  
  for i in range(max_move_count+1): 
    master_move[i] = dict()
    with open(f"{move_folder}/{str(i)}.json") as json_file:  
      i_move_dict = json.load(json_file)["persona"]
      for p in persona_names:
        # Agents that SKIPped a step (LLM timeout) are omitted from that step's
        # movement file. Skip them — they keep their previous position.
        if p not in i_move_dict:
          continue
        cur = i_move_dict[p]
        prev = persona_last_move.get(p)
        if (prev is None
            or cur["movement"] != prev["movement"]
            or cur["pronunciatio"] != prev["pronunciatio"]
            or cur["description"] != prev["description"]
            or cur["chat"] != prev["chat"]):
          persona_last_move[p] = {"movement": cur["movement"],
                                  "pronunciatio": cur["pronunciatio"],
                                  "description": cur["description"],
                                  "chat": cur["chat"]}
          master_move[i][p] = persona_last_move[p]


  create_folder_if_not_there(compressed_storage)
  with open(f"{compressed_storage}/master_movement.json", "w") as outfile:
    outfile.write(json.dumps(master_move, indent=2))

  shutil.copyfile(meta_file, f"{compressed_storage}/meta.json")
  shutil.copytree(persona_folder, f"{compressed_storage}/personas/")


if __name__ == '__main__':
  compress("July1_the_ville_isabella_maria_klaus-step-3-9")









  











