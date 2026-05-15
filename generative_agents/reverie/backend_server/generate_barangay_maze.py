"""
generate_barangay_maze.py

Generates all maze CSV files and special_blocks CSVs for the Barangay Mabuhay world.
Run from reverie/backend_server/:  python generate_barangay_maze.py

Output goes to:
  ../../environment/frontend_server/static_dirs/assets/barangay/matrix/
"""
import os
import json

# ---------------------------------------------------------------------------
# World dimensions
# ---------------------------------------------------------------------------
W, H = 80, 60          # width × height in tiles
COLLISION = "32125"     # tile ID used for impassable walls (matches utils.py)
EMPTY = "0"

# ---------------------------------------------------------------------------
# Tile ID assignments
# World block
WORLD_ID   = "34001"
# Sector IDs
SEC = {
    "munhall":    "34010",
    "bgyhall":    "34011",
    "audit":      "34012",
    "police":     "34013",
    "school":     "34014",
    "church":     "34015",
    "resA":       "34016",
    "farm":       "34017",
    "market":     "34018",
    "media":      "34019",
    "hospital":   "34020",
    "contoffice": "34021",
    "resB":       "34022",
    "resC":       "34023",
    "park":       "34024",
}
# Arena IDs (sector + arena sub-area)
ARENA = {
    "munhall_office":     "34110",
    "munhall_council":    "34111",
    "bgyhall_office":     "34112",
    "bgyhall_hall":       "34113",
    "audit_office":       "34114",
    "police_station":     "34115",
    "school_classroom":   "34116",
    "school_library":     "34117",
    "church_chapel":      "34118",
    "resA_home":          "34119",
    "farm_field":         "34120",
    "market_stall":       "34121",
    "media_newsroom":     "34122",
    "hospital_clinic":    "34123",
    "cont_office":        "34124",
    "resB_home":          "34125",
    "resC_home":          "34126",
    "park_garden":        "34127",
}
# Game object IDs
OBJ = {
    "mayor_desk":        "34201",
    "council_table":     "34202",
    "captain_desk":      "34203",
    "auditor_desk":      "34204",
    "officer_desk":      "34205",
    "teacher_desk":      "34206",
    "altar":             "34207",
    "crop_field":        "34208",
    "vendor_stall":      "34209",
    "journalist_desk":   "34210",
    "nurse_station":     "34211",
    "contractor_desk":   "34212",
    "park_bench":        "34213",
    "bed":               "34214",
    "basketball_court":  "34215",
}
# Spawning location IDs (one per zone, for agent placement)
SPAWN = {
    "munhall":    "34301",
    "bgyhall":    "34302",
    "audit":      "34303",
    "police":     "34304",
    "school":     "34305",
    "church":     "34306",
    "resA":       "34307",
    "farm":       "34308",
    "market":     "34309",
    "media":      "34310",
    "hospital":   "34311",
    "contoffice": "34312",
    "resB":       "34313",
    "resC":       "34314",
    "park":       "34315",
}

# ---------------------------------------------------------------------------
# Barangay layout: list of (row_start, row_end, col_start, col_end, zone_key)
# Coordinates are inclusive tile ranges.
# ---------------------------------------------------------------------------
ZONES = [
    # Government cluster (top-left)
    (2,  12, 2,  14, "munhall"),
    (2,  12, 16, 24, "bgyhall"),
    (2,  12, 26, 33, "audit"),
    (2,  12, 35, 42, "police"),

    # Education & religion (top-right)
    (2,  18, 45, 58, "school"),
    (2,  18, 61, 75, "church"),

    # Residential Zone A (middle-left)
    (15, 35, 2,  22, "resA"),

    # Farm (middle-center)
    (15, 38, 25, 45, "farm"),

    # Market + Media (middle-right)
    (20, 35, 48, 60, "market"),
    (20, 35, 63, 75, "media"),

    # Health center + Contractor (lower-center-left)
    (40, 55, 2,  18, "hospital"),
    (40, 55, 21, 36, "contoffice"),

    # Residential Zones B & C (lower)
    (40, 57, 39, 54, "resB"),
    (40, 57, 57, 75, "resC"),

    # Plaza / park (center bottom)
    (42, 55, 26, 36, "park"),
]

# Arena sub-regions (must be inside parent zone)
ARENAS = [
    # Municipal Hall arenas
    (3,  7,  3,  10, "munhall_office"),
    (3,  7,  11, 14, "munhall_council"),
    # Barangay Hall arenas
    (3,  7,  17, 20, "bgyhall_office"),
    (3,  7,  21, 24, "bgyhall_hall"),
    # Audit
    (3,  8,  27, 33, "audit_office"),
    # Police
    (3,  8,  36, 42, "police_station"),
    # School
    (3, 10,  46, 54, "school_classroom"),
    (11,17,  46, 58, "school_library"),
    # Church
    (3, 17,  62, 75, "church_chapel"),
    # ResA homes
    (16,34,  3,  22, "resA_home"),
    # Farm
    (16,37,  26, 45, "farm_field"),
    # Market
    (21,34,  49, 60, "market_stall"),
    # Media
    (21,34,  64, 75, "media_newsroom"),
    # Hospital
    (41,54,  3,  18, "hospital_clinic"),
    # Contractor
    (41,54,  22, 36, "cont_office"),
    # ResB
    (41,56,  40, 54, "resB_home"),
    # ResC
    (41,56,  58, 75, "resC_home"),
    # Park
    (43,54,  27, 36, "park_garden"),
]

# Game objects: (row, col, obj_key)
OBJECTS = [
    (5,  6,  "mayor_desk"),
    (5,  12, "council_table"),
    (5,  18, "captain_desk"),
    (5,  28, "auditor_desk"),
    (5,  37, "officer_desk"),
    (5,  48, "teacher_desk"),
    (5,  65, "altar"),
    (20, 30, "crop_field"),
    (25, 52, "vendor_stall"),
    (24, 66, "journalist_desk"),
    (43, 8,  "nurse_station"),
    (43, 25, "contractor_desk"),
    (47, 30, "park_bench"),
    (47, 33, "basketball_court"),
    (20, 8,  "bed"),   # resA representative
    (46, 44, "bed"),   # resB representative
    (46, 62, "bed"),   # resC representative
]

# Spawn points: (row, col, zone_key)  — one per zone near zone center
SPAWNS = [
    (4,  8,  "munhall"),
    (4,  20, "bgyhall"),
    (4,  30, "audit"),
    (4,  38, "police"),
    (8,  50, "school"),
    (8,  67, "church"),
    (25, 12, "resA"),
    (26, 35, "farm"),
    (27, 54, "market"),
    (27, 68, "media"),
    (47, 10, "hospital"),
    (47, 28, "contoffice"),
    (48, 46, "resB"),
    (48, 65, "resC"),
    (49, 31, "park"),
]

# ---------------------------------------------------------------------------
# Helper: fill a flat grid
# ---------------------------------------------------------------------------
def make_grid(default=EMPTY):
    return [[default] * W for _ in range(H)]

def set_rect(grid, r1, r2, c1, c2, val):
    for r in range(r1, min(r2+1, H)):
        for c in range(c1, min(c2+1, W)):
            grid[r][c] = val

def set_border(grid, r1, r2, c1, c2, val):
    """Set only the border of a rectangle."""
    for c in range(c1, min(c2+1, W)):
        if r1 < H: grid[r1][c] = val
        if r2 < H: grid[r2][c] = val
    for r in range(r1, min(r2+1, H)):
        if c1 < W: grid[r][c1] = val
        if c2 < W: grid[r][c2] = val

def flat(grid):
    """Flatten 2D grid to single CSV row."""
    row = []
    for r in grid:
        row.extend(r)
    return ",".join(row)

# ---------------------------------------------------------------------------
# Build the grids
# ---------------------------------------------------------------------------
collision_grid = make_grid(EMPTY)
sector_grid    = make_grid(EMPTY)
arena_grid     = make_grid(EMPTY)
obj_grid       = make_grid(EMPTY)
spawn_grid     = make_grid(EMPTY)

# World boundary walls
set_border(collision_grid, 0, H-1, 0, W-1, COLLISION)

# Fill zones with sector IDs and draw walls around each zone
for r1, r2, c1, c2, zkey in ZONES:
    set_rect(sector_grid, r1, r2, c1, c2, SEC[zkey])
    set_border(collision_grid, r1, r2, c1, c2, COLLISION)

# Fill arena sub-regions
for r1, r2, c1, c2, akey in ARENAS:
    set_rect(arena_grid, r1, r2, c1, c2, ARENA[akey])

# Place game objects (single tile)
for r, c, okey in OBJECTS:
    if 0 <= r < H and 0 <= c < W:
        obj_grid[r][c] = OBJ[okey]

# Place spawning locations (single tile)
for r, c, skey in SPAWNS:
    if 0 <= r < H and 0 <= c < W:
        spawn_grid[r][c] = SPAWN[skey]

# ---------------------------------------------------------------------------
# Write output files
# ---------------------------------------------------------------------------
OUT_ROOT = os.path.abspath(os.path.join(
    os.path.dirname(__file__),
    "../../environment/frontend_server/static_dirs/assets/barangay/matrix"
))
os.makedirs(os.path.join(OUT_ROOT, "maze"),           exist_ok=True)
os.makedirs(os.path.join(OUT_ROOT, "special_blocks"), exist_ok=True)

def write(path, content):
    with open(path, "w") as f:
        f.write(content)
    print(f"  wrote {path}")

# maze_meta_info.json
write(os.path.join(OUT_ROOT, "maze_meta_info.json"), json.dumps({
    "world_name": "Barangay Mabuhay",
    "maze_width": W,
    "maze_height": H,
    "sq_tile_size": 32,
    "special_constraint": "",
}, indent=2))

# maze CSVs (flat single-row)
maze_dir = os.path.join(OUT_ROOT, "maze")
write(os.path.join(maze_dir, "collision_maze.csv"),          flat(collision_grid))
write(os.path.join(maze_dir, "sector_maze.csv"),             flat(sector_grid))
write(os.path.join(maze_dir, "arena_maze.csv"),              flat(arena_grid))
write(os.path.join(maze_dir, "game_object_maze.csv"),        flat(obj_grid))
write(os.path.join(maze_dir, "spawning_location_maze.csv"),  flat(spawn_grid))

# special_blocks CSVs
sb_dir = os.path.join(OUT_ROOT, "special_blocks")

# world_blocks.csv
write(os.path.join(sb_dir, "world_blocks.csv"),
      f"{WORLD_ID}, Barangay Mabuhay\n")

# sector_blocks.csv — format: "tile_id, World, Sector"
sector_names = {
    "munhall":    "Municipal Hall",
    "bgyhall":    "Barangay Hall",
    "audit":      "Audit Office",
    "police":     "Police Station",
    "school":     "School",
    "church":     "Church",
    "resA":       "Residential Zone A",
    "farm":       "Farm Area",
    "market":     "Public Market",
    "media":      "Media Office",
    "hospital":   "Health Center",
    "contoffice": "Contractor Office",
    "resB":       "Residential Zone B",
    "resC":       "Residential Zone C",
    "park":       "Plaza",
}
sec_rows = [f"{SEC[k]}, Barangay Mabuhay, {v}" for k, v in sector_names.items()]
write(os.path.join(sb_dir, "sector_blocks.csv"), "\n".join(sec_rows) + "\n")

# arena_blocks.csv — format: "tile_id, World, Sector, Arena"
arena_meta = {
    "munhall_office":  ("Municipal Hall",    "office"),
    "munhall_council": ("Municipal Hall",    "council room"),
    "bgyhall_office":  ("Barangay Hall",     "office"),
    "bgyhall_hall":    ("Barangay Hall",     "session hall"),
    "audit_office":    ("Audit Office",      "office"),
    "police_station":  ("Police Station",    "station"),
    "school_classroom":("School",            "classroom"),
    "school_library":  ("School",            "library"),
    "church_chapel":   ("Church",            "chapel"),
    "resA_home":       ("Residential Zone A","home"),
    "farm_field":      ("Farm Area",         "field"),
    "market_stall":    ("Public Market",     "stall"),
    "media_newsroom":  ("Media Office",      "newsroom"),
    "hospital_clinic": ("Health Center",     "clinic"),
    "cont_office":     ("Contractor Office", "office"),
    "resB_home":       ("Residential Zone B","home"),
    "resC_home":       ("Residential Zone C","home"),
    "park_garden":     ("Plaza",             "park"),
}
arena_rows = [
    f"{ARENA[k]}, Barangay Mabuhay, {sector}, {arena}"
    for k, (sector, arena) in arena_meta.items()
]
write(os.path.join(sb_dir, "arena_blocks.csv"), "\n".join(arena_rows) + "\n")

# game_object_blocks.csv — format: "tile_id, World, Sector, Arena, Object"
obj_meta = {
    "mayor_desk":      ("Municipal Hall",    "office",       "mayor's desk"),
    "council_table":   ("Municipal Hall",    "council room", "council table"),
    "captain_desk":    ("Barangay Hall",     "office",       "captain's desk"),
    "auditor_desk":    ("Audit Office",      "office",       "auditor's desk"),
    "officer_desk":    ("Police Station",    "station",      "officer's desk"),
    "teacher_desk":    ("School",            "classroom",    "teacher's desk"),
    "altar":           ("Church",            "chapel",       "altar"),
    "crop_field":      ("Farm Area",         "field",        "crop field"),
    "vendor_stall":    ("Public Market",     "stall",        "vendor stall"),
    "journalist_desk": ("Media Office",      "newsroom",     "journalist's desk"),
    "nurse_station":   ("Health Center",     "clinic",       "nurse's station"),
    "contractor_desk": ("Contractor Office", "office",       "contractor's desk"),
    "park_bench":      ("Plaza",             "park",         "park bench"),
    "basketball_court":("Plaza",             "park",         "basketball court"),
    "bed":             ("Residential Zone A","home",         "bed"),
}
obj_rows = [
    f"{OBJ[k]}, Barangay Mabuhay, {sector}, {arena}, {obj}"
    for k, (sector, arena, obj) in obj_meta.items()
]
write(os.path.join(sb_dir, "game_object_blocks.csv"), "\n".join(obj_rows) + "\n")

# spawning_location_blocks.csv — format: "tile_id, World, Sector, Arena, SpawnLabel"
spawn_arena = {
    "munhall":    ("Municipal Hall",    "office"),
    "bgyhall":    ("Barangay Hall",     "office"),
    "audit":      ("Audit Office",      "office"),
    "police":     ("Police Station",    "station"),
    "school":     ("School",            "classroom"),
    "church":     ("Church",            "chapel"),
    "resA":       ("Residential Zone A","home"),
    "farm":       ("Farm Area",         "field"),
    "market":     ("Public Market",     "stall"),
    "media":      ("Media Office",      "newsroom"),
    "hospital":   ("Health Center",     "clinic"),
    "contoffice": ("Contractor Office", "office"),
    "resB":       ("Residential Zone B","home"),
    "resC":       ("Residential Zone C","home"),
    "park":       ("Plaza",             "park"),
}
spawn_rows = [
    f"{SPAWN[k]}, Barangay Mabuhay, {sector}, {arena}, {sector} spawn"
    for k, (sector, arena) in spawn_arena.items()
]
write(os.path.join(sb_dir, "spawning_location_blocks.csv"), "\n".join(spawn_rows) + "\n")

print(f"\nBarangay Mabuhay maze generated ({W}x{H} tiles).")
print(f"Output: {OUT_ROOT}")
