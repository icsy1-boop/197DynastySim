"""
barangay_mechanics.py

Barangay-specific simulation mechanics layered on top of generative_agents.
Provides:
  1. Dynasty trust initialization — agents in the same family start with
     positive relationship memories toward each other. (Bootstrap seeds this
     too; the runtime call was removed from reverie — see inject_dynasty_memories.)
  2. World metrics as a READOUT of the population's memory stream: corruption,
     welfare (mean of per-agent satisfaction), unrest (share of personally
     aggrieved agents) — plus per-agent readout helpers (memory masses, trust
     toward named officials, population-level blame) used by the protest,
     election, and news modules.

Usage (called from reverie.py):
  from barangay_mechanics import log_corruption_step, load_agent_rows, ...
"""
import csv
import os
import json
import math
import datetime

from barangay_roles import OFFICIAL_ROLES

# Welfare & unrest are integrated world state: each logging tick they drift
# toward a memory-derived target rather than snapping, so the community
# condition evolves over weeks. Rates are per 10-step logging tick (env-tunable).
_WELFARE_RATE = float(os.environ.get("WELFARE_RATE", 0.08))
_UNREST_RATE  = float(os.environ.get("UNREST_RATE", 0.10))

# ---------------------------------------------------------------------------
# 1. Dynasty Trust Initialization
# ---------------------------------------------------------------------------

def load_agent_family_map(csv_path):
    """
    Returns dict: {agent_name: family_id} for agents with a non-null family_id.
    Also returns dict: {family_id: [agent_names]} for group lookups.
    """
    name_to_family = {}
    family_to_names = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["name"].strip()
            fid  = row.get("family_id", "").strip()
            if fid:
                name_to_family[name] = fid
                family_to_names.setdefault(fid, []).append(name)
    return name_to_family, family_to_names


def inject_dynasty_memories(personas, csv_path):
    """
    For each agent in a political dynasty (same family_id), inject an initial
    memory into every family member's associative memory describing their bond.

    NOTE: no longer called from reverie — bootstrap (barangay_init) already
    seeds family trust, and this call had a broken add_thought signature that
    injected nothing while spamming logs. Kept (fixed) for manual/bootstrap use.
    """
    if not os.path.exists(csv_path):
        print(f"[barangay] CSV not found at {csv_path}, skipping dynasty init.")
        return

    name_to_family, family_to_names = load_agent_family_map(csv_path)
    injected = 0

    for persona_name, persona in personas.items():
        fid = name_to_family.get(persona_name)
        if not fid:
            continue

        family_members = [n for n in family_to_names[fid] if n != persona_name
                          and n in personas]
        if not family_members:
            continue

        for member_name in family_members:
            desc = (f"{persona_name} and {member_name} are members of the "
                    f"{fid} political family. They share a strong bond of "
                    f"trust and loyalty.")
            try:
                persona.a_mem.add_thought(
                    persona.scratch.curr_time or datetime.datetime(2024, 2, 13, 7, 0, 0),
                    None,                                   # expiration
                    persona_name, "is family with", member_name,
                    desc,
                    {persona_name, member_name, fid, "family", "trust"},
                    8,                                      # poignancy
                    (desc, [0.0] * 768),
                    [])
                injected += 1
            except Exception as e:
                print(f"[barangay] Could not inject dynasty memory for "
                      f"{persona_name}<->{member_name}: {e}")

    print(f"[barangay] Dynasty memories injected: {injected} relationships.")


# ---------------------------------------------------------------------------
# 2. Memory-stream classification (keyword pre-pass + embedding similarity)
# ---------------------------------------------------------------------------
# World metrics summarise what the population actually CARRIES in memory:
# corruption/scandal memories push corruption up and welfare down; governance/
# relief/reform memories push the other way; grievance/protest memories drive
# unrest. Classification: fast keyword pass first, then embedding similarity
# against anchor texts (robust to Taglish and free LLM phrasing — every node
# already stores an embedding, so this costs no extra endpoint calls at
# readout time). Results are cached per node (classification is immutable).

_CLASS_KW = {
    "corruption": {"corruption", "scandal", "bribe", "kickback"},
    "governance": {"governance", "praise", "service", "reform"},
    "grievance":  {"protest", "anger", "grievance"},
}
_CLASS_TEXT = {
    "corruption": ("bribe", "embezzle", "kickback", "ghost project", "divert",
                   "stole", "steal", "corrupt", "scandal", "misappropriat",
                   "nepotism", "pocketed", "overpric", "anomal"),
    "governance": ("reform", "relief", "delivered", "transparency", "open bidding",
                   "audit", "finished the", "completed the", "scholarship",
                   "honest", "fairly", "served residents", "good news"),
    "grievance":  ("angry", "furious", "starving", "unfair", "fed up", "fed-up",
                   "injustice", "protest", "rally", "betray", "neglect", "no service"),
}
_ANCHOR_TEXTS = {
    "corruption": (
        "an official took a bribe and pocketed public funds in a corruption scandal",
        "kickbacks, overpriced supplies and a ghost project — government money was stolen",
    ),
    "governance": (
        "an official honestly delivered public services, relief goods and reforms to residents",
        "transparent open bidding and a completed community project; residents praise good governance",
    ),
    "grievance":  (
        "residents are angry and fed up with injustice and neglect by their officials",
        "we were betrayed, there are no services for us, people want to rally in protest",
    ),
}
_MEM_HALFLIFE_H = float(os.environ.get("METRIC_MEM_HALFLIFE_H", 168.0))  # 7 sim-days
_MEM_WINDOW_H   = float(os.environ.get("METRIC_MEM_WINDOW_H", 336.0))    # 14 sim-days
_EMBED_CLASS_TH = float(os.environ.get("METRIC_EMBED_CLASS_TH", 0.66))
# Aggrieved = personal GRIEVANCE mass only (victim/protest/anger memories —
# lived harm). Corruption-class mass is knowledge of corruption, not harm; it
# saturates the population once a scandal hits the media, so it must NOT count
# toward marching (measured Jul 2026: with a 0.5·corr term, one scandal made
# 467/500 "aggrieved"). One poignancy-8 fresh victim memory ≈ mass 8 → the
# default 6.0 means one strong lived grievance makes an agent protest-willing.
_AGGRIEVED_TH   = float(os.environ.get("UNREST_PERSONAL_TH", 6.0))
_MEM_SAT_SHIFT  = float(os.environ.get("MEM_SAT_SHIFT", 0.25))

_anchor_embs = None            # {label: [vec, ...]} — embedded once, on demand
_node_class_cache = {}         # (persona_name, node_id) -> label|None


def _get_anchor_embs():
    """Embed the anchor texts once. On endpoint failure return {} WITHOUT
    caching, so the next tick retries instead of degrading forever."""
    global _anchor_embs
    if _anchor_embs is not None:
        return _anchor_embs
    try:
        from persona.prompt_template.gpt_structure import get_embedding
        embs = {}
        for label, texts in _ANCHOR_TEXTS.items():
            embs[label] = [get_embedding(t) for t in texts]
        _anchor_embs = embs
        return _anchor_embs
    except Exception as e:
        print(f"[METRICS] anchor embedding unavailable ({e}); keyword-only pass",
              flush=True)
        return {}


def _cos(a, b):
    num = 0.0
    da = 0.0
    db = 0.0
    for x, y in zip(a, b):
        num += x * y
        da += x * x
        db += y * y
    if da <= 0.0 or db <= 0.0:
        return 0.0
    return num / math.sqrt(da * db)


def _classify_node(node, persona=None):
    """Label a memory node corruption/governance/grievance/None.
    Keyword pass -> description-text pass -> embedding-similarity pass."""
    cache_key = (persona.scratch.name if persona is not None else "?",
                 getattr(node, "node_id", id(node)))
    if cache_key in _node_class_cache:
        return _node_class_cache[cache_key]

    label = None
    kws = set(k.lower() for k in (node.keywords or []))
    for lbl, kwset in _CLASS_KW.items():
        if kws & kwset:
            label = lbl
            break
    if label is None:
        desc = (node.description or "").lower()
        for lbl, words in _CLASS_TEXT.items():
            if any(w in desc for w in words):
                label = lbl
                break
    if label is None and persona is not None:
        emb = persona.a_mem.embeddings.get(getattr(node, "embedding_key", None))
        if emb:
            anchors = _get_anchor_embs()
            best_lbl, best_sim = None, 0.0
            for lbl, vecs in anchors.items():
                for v in vecs:
                    s = _cos(emb, v)
                    if s > best_sim:
                        best_lbl, best_sim = lbl, s
            if best_sim >= _EMBED_CLASS_TH:
                label = best_lbl

    _node_class_cache[cache_key] = label
    return label


def agent_memory_masses(persona, curr_time):
    """Recency- and poignancy-weighted corruption/governance/grievance mass of
    ONE agent's memory (events + thoughts + chats), deduped by description so
    an injected broadcast counts once per agent. seq_* lists are newest-first,
    so the scan stops at the window edge instead of walking all history."""
    mass = {"corruption": 0.0, "governance": 0.0, "grievance": 0.0}
    am = getattr(persona, "a_mem", None)
    if am is None:
        return mass
    seen = set()
    for seq in (getattr(am, "seq_event", []), getattr(am, "seq_thought", []),
                getattr(am, "seq_chat", [])):
        for n in seq:
            if curr_time is not None and getattr(n, "created", None) is not None:
                age_h = (curr_time - n.created).total_seconds() / 3600.0
                if age_h < 0:
                    continue
                if age_h > _MEM_WINDOW_H:
                    break               # newest-first: everything after is older
                decay = 0.5 ** (age_h / _MEM_HALFLIFE_H)
            else:
                decay = 1.0
            label = _classify_node(n, persona)
            if not label:
                continue
            desc = (n.description or "").strip()
            if desc in seen:
                continue
            seen.add(desc)
            mass[label] += float(getattr(n, "poignancy", 1)) * decay
    return mass


def name_trust(persona, names, curr_time):
    """Per-(agent, name) trust readout: signed poignancy×recency mass of this
    agent's classified memories that mention each name (governance positive,
    corruption/grievance negative). Returns {name: score}. This one readout
    feeds vote fail-safes, protest blame, and survey defaults."""
    scores = {n: 0.0 for n in names}
    am = getattr(persona, "a_mem", None)
    if am is None or not names:
        return scores
    lowered = [(n, n.lower()) for n in names]
    for seq in (getattr(am, "seq_event", []), getattr(am, "seq_thought", []),
                getattr(am, "seq_chat", [])):
        for node in seq:
            if curr_time is not None and getattr(node, "created", None) is not None:
                age_h = (curr_time - node.created).total_seconds() / 3600.0
                if age_h < 0:
                    continue
                if age_h > _MEM_WINDOW_H:
                    break
                decay = 0.5 ** (age_h / _MEM_HALFLIFE_H)
            else:
                decay = 1.0
            label = _classify_node(node, persona)
            if not label:
                continue
            desc = (node.description or "").lower()
            if not desc:
                continue
            w = float(getattr(node, "poignancy", 1)) * decay
            sign = 1.0 if label == "governance" else -1.0
            for orig, low in lowered:
                if low in desc:
                    scores[orig] += sign * w
    return scores


def population_blame(personas, official_names, curr_time, top_k=3):
    """Officials most present in the population's negative (corruption/
    grievance) memories — the memory-derived answer to 'who do residents hold
    responsible', replacing random incumbent blame. Returns [(name, score)]
    strongest-first, only names with score > 0."""
    totals = {n: 0.0 for n in official_names}
    for persona in personas.values():
        t = name_trust(persona, official_names, curr_time)
        for n, v in t.items():
            if v < 0:
                totals[n] += -v
    ranked = sorted(((n, s) for n, s in totals.items() if s > 0),
                    key=lambda x: x[1], reverse=True)
    return ranked[:top_k]


# ---------------------------------------------------------------------------
# 2b. World metrics readout + CSV log
# ---------------------------------------------------------------------------

_FORMULA_VERSION = "mem2"
_CSV_FIELDS_V1 = ["step", "datetime", "corruption_index", "dynasty_bonus",
                  "welfare", "unrest"]
_CSV_FIELDS_V2 = _CSV_FIELDS_V1 + ["corr_mass", "gov_mass", "grv_mass",
                                   "aggrieved_share", "formula"]


def _csv_fields_for(log_file):
    """Existing logs keep their column set (old parsers stay valid); new logs
    get the extended, version-stamped columns."""
    if os.path.exists(log_file):
        try:
            with open(log_file, newline="") as f:
                header = f.readline().strip().split(",")
            if "formula" not in header:
                return _CSV_FIELDS_V1, False
        except Exception:
            pass
        return _CSV_FIELDS_V2, False
    return _CSV_FIELDS_V2, True


def log_corruption_step(personas, agent_rows_by_name, step, curr_time, output_path,
                        event_bonus=0.0, prev_metrics=None):
    """
    Read the population's memory stream into world metrics and append them to
    <output_path>/corruption_log.csv. (Signature kept for reverie; the
    `event_bonus` argument is accepted but ignored — metrics are a readout.)

    corruption = corr_mass / (corr_mass + gov_mass)      (reputation balance)
    welfare    = mean per-agent satisfaction: CSV prior shifted by the agent's
                 OWN memory balance (governance minus corruption+grievance)
    unrest     = share of agents whose personal grievance mass crosses
                 UNREST_PERSONAL_TH (i.e. how many people are actually angry)

    Returns dict: {corruption_index, welfare_score, unrest, dynasty_bonus, ...}.
    """
    os.makedirs(output_path, exist_ok=True)
    log_file = os.path.join(output_path, "corruption_log.csv")
    prev = prev_metrics or {}
    eps = 1e-6

    # --- per-agent + population memory masses ---
    total = {"corruption": 0.0, "governance": 0.0, "grievance": 0.0}
    per_agent = {}
    for name, persona in personas.items():
        m = agent_memory_masses(persona, curr_time)
        per_agent[name] = m
        for k in total:
            total[k] += m[k]
    corr, gov, grv = total["corruption"], total["governance"], total["grievance"]

    # corruption salience: bad vs good official-reputation memory.
    if corr + gov < eps:
        corruption_target = float(prev.get("corruption_index", 0.5))
        print(f"[METRICS] step {step}: no corruption/governance memory signal "
              f"in {_MEM_WINDOW_H:.0f}h window — corruption holds at "
              f"{corruption_target:.3f} (check decision ticks / classifier)",
              flush=True)
    else:
        corruption_target = corr / (corr + gov + eps)

    # welfare: mean of per-agent satisfaction (CSV prior +/- own memory balance)
    sats = []
    n_aggrieved = 0
    n_scored = 0
    for name, m in per_agent.items():
        row = agent_rows_by_name.get(name)
        if not row:
            continue
        n_scored += 1
        try:
            prior = float(row.get("satisfaction", 50)) / 100.0
        except (TypeError, ValueError):
            prior = 0.5
        c_i, g_i, r_i = m["corruption"], m["governance"], m["grievance"]
        tot_i = c_i + g_i + r_i
        if tot_i > eps:
            balance = (g_i - c_i - r_i) / tot_i          # -1 .. +1
            sat_i = prior + _MEM_SAT_SHIFT * balance
        else:
            sat_i = prior
        sats.append(max(0.0, min(1.0, sat_i)))
        if r_i >= _AGGRIEVED_TH:
            n_aggrieved += 1

    welfare_target = (sum(sats) / len(sats)) if sats else 0.5
    aggrieved_share = (n_aggrieved / n_scored) if n_scored else 0.0
    unrest_target = max(0.0, min(1.0, aggrieved_share))

    # Light smoothing toward the memory readout (stability, not a fixed target).
    corruption_index = max(0.0, min(1.0,
        float(prev.get("corruption_index", corruption_target))
        + _WELFARE_RATE * (corruption_target - float(prev.get("corruption_index", corruption_target)))))
    welfare_score = max(0.0, min(1.0,
        float(prev.get("welfare_score", welfare_target))
        + _WELFARE_RATE * (welfare_target - float(prev.get("welfare_score", welfare_target)))))
    unrest = max(0.0, min(1.0,
        float(prev.get("unrest", unrest_target))
        + _UNREST_RATE * (unrest_target - float(prev.get("unrest", unrest_target)))))

    # Dynasty seat-share kept as a logged DIAGNOSTIC (not folded into corruption).
    family_in_office = {}
    for name in personas:
        row = agent_rows_by_name.get(name)
        if not row:
            continue
        role = getattr(personas[name].scratch, "role", None) or row.get("role", "")
        if role in OFFICIAL_ROLES and row.get("family_id", "").strip():
            fid = row["family_id"].strip()
            family_in_office[fid] = family_in_office.get(fid, 0) + 1
    dynasty_bonus = sum((c - 1) * 0.05 for c in family_in_office.values() if c >= 2)

    fields, write_header = _csv_fields_for(log_file)
    row_all = {
        "step": step,
        "datetime": curr_time.strftime("%Y-%m-%d %H:%M:%S"),
        "corruption_index": f"{corruption_index:.4f}",
        "dynasty_bonus": f"{dynasty_bonus:.4f}",
        "welfare": f"{welfare_score:.4f}",
        "unrest": f"{unrest:.4f}",
        "corr_mass": f"{corr:.1f}",
        "gov_mass": f"{gov:.1f}",
        "grv_mass": f"{grv:.1f}",
        "aggrieved_share": f"{aggrieved_share:.4f}",
        "formula": _FORMULA_VERSION,
    }
    with open(log_file, "a", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(fields)
        writer.writerow([row_all[k] for k in fields])

    # Carry forward any extra state (recent_events, election_step) so the
    # 10-step recompute doesn't drop it, then overwrite the computed fields.
    result = dict(prev)
    result.update({"corruption_index": corruption_index, "welfare_score": welfare_score,
                   "unrest": unrest, "dynasty_bonus": dynasty_bonus,
                   "welfare_target": welfare_target, "unrest_target": unrest_target,
                   "corr_mass": corr, "gov_mass": gov, "grv_mass": grv,
                   "aggrieved_share": aggrieved_share})
    return result


# ---------------------------------------------------------------------------
# 3. Per-sim world-metrics persistence (survives autosave / VM reboot)
# ---------------------------------------------------------------------------

def load_world_metrics(metrics_dir):
    """Load integrated world metrics from <metrics_dir>/world_metrics.json (or {})."""
    path = os.path.join(metrics_dir, "world_metrics.json")
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_world_metrics(metrics_dir, metrics):
    """Persist integrated world metrics so welfare/unrest accumulate across reboots."""
    try:
        os.makedirs(metrics_dir, exist_ok=True)
        with open(os.path.join(metrics_dir, "world_metrics.json"), "w") as f:
            json.dump(metrics, f, indent=2)
    except Exception:
        pass


def load_agent_rows(csv_path):
    """
    Load barangay_agents.csv into a dict keyed by agent name.
    Call once at sim startup.
    """
    rows = {}
    if not os.path.exists(csv_path):
        return rows
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows[row["name"].strip()] = row
    return rows
