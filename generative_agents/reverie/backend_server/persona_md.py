"""
persona_md.py — make each agent's Markdown file (personas/<name>.md) the editable
source of truth for role, identity, and the dynamism-relevant attributes.

Two directions:
  * write-back: whenever the sim changes an agent (e.g. an election win/loss),
    apply_role() updates the persona's role + the identity fields that actually
    drive their daily plan (lifestyle / currently / daily_plan_req), then
    write_md() persists the new state to the .md.
  * read-back: reload_md() re-seeds a persona from its .md. reverie calls it at
    the start of each sim-day, mtime-gated, so a .md edited mid-run (manually or
    by the sim) takes effect the next day without clobbering unedited agents.

This is what makes a demoted official actually stop reporting to Barangay Hall and
a new winner take up their office, and lets you hand-edit a .md to steer/observe.
"""
import os, re, logging

logger = logging.getLogger(__name__)

# Default (legacy) location. IMPORTANT: this global dir leaked role state ACROSS
# sims — one sim's election demotions re-seeded every later sim at its first
# day-boundary reload (the mtime cache is empty on process start, so every .md
# counted as "changed"). reverie now calls set_md_dir(<sim_folder>/personas_md)
# at startup so each sim reads/writes only its own .md files.
PERSONAS_DIR = os.path.join(os.path.dirname(__file__), "personas")
_md_dir = PERSONAS_DIR


def set_md_dir(path):
    """Point the .md store at a per-sim directory (called by reverie at init).
    Fresh forks start empty — no cross-sim carry-over; the sim's own elections
    (and manual edits) populate it."""
    global _md_dir
    _md_dir = path
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as e:
        logger.warning(f"[MD] could not create md dir {path}: {e}")
    _last_mtime.clear()

# Section title (in the .md) -> Scratch attribute it maps to.
_MD_SECTIONS = {
    "Personality":   "innate",
    "Background":     "learned",
    "Current Goals":  "currently",
    "Daily Routine":  "lifestyle",
    "Daily Plan":     "daily_plan_req",
}
# Numeric, dynamism-relevant attributes round-tripped via an "## Attributes"
# section; these live in the agent CSV row (used by corruption/election/news).
_ATTR_KEYS = ["greed", "integrity", "ambition", "family_loyalty",
              "satisfaction", "initial_trust_score"]

OFFICIAL_ROLES = {"mayor", "vice_mayor", "councilor", "barangay_captain",
                  "barangay_kagawad", "barangay_treasurer", "barangay_secretary"}

# Remember the .md mtime we last applied, so reload only re-seeds changed files.
_last_mtime = {}


def _md_path(name):
    return os.path.join(_md_dir, f"{name}.md")


def _role_schedule(role):
    """Daily-routine summary for a role (from barangay_init), lazily imported to
    avoid pulling barangay_init's world-loading into reverie startup."""
    try:
        from barangay_init import ROLE_SCHEDULE, WORLD_NAME
        return (ROLE_SCHEDULE.get(role,
                "follows a typical daily routine based on their role."), WORLD_NAME)
    except Exception:
        return ("follows a typical daily routine based on their role.",
                "barangay_mabuhay")


def seed_md(personas, agent_rows_by_name):
    """Ensure every persona has an editable .md in the current md dir — the
    .md is the hand-editable source of truth for role/identity/attributes, so
    a fresh fork (empty per-sim dir) must expose one file per agent from step
    0. Existing files are left untouched (they may carry the sim's own election
    write-backs or manual edits)."""
    n = 0
    for name, persona in personas.items():
        try:
            if not os.path.exists(_md_path(name)):
                write_md(persona, agent_rows_by_name.get(name))
                n += 1
        except Exception as e:
            logger.warning(f"[MD] seed failed for {name}: {e}")
    if n:
        print(f"[MD] seeded {n} editable persona .md files in {_md_dir}", flush=True)
    return n


def apply_role(persona, row, new_role):
    """Change a persona's role AND the identity fields that drive their daily
    plan, so the role change actually changes what they do / where they go."""
    s = persona.scratch
    sched, world = _role_schedule(new_role)
    role_disp = new_role.replace("_", " ")
    s.role = new_role
    s.agent_tier = 1 if (new_role in OFFICIAL_ROLES or new_role == "civil_servant_admin") \
                    else getattr(s, "agent_tier", 1)
    if row is not None:
        row["role"] = new_role
    s.lifestyle = f"{s.name} wakes up around 6am, {sched} Goes to bed around 10pm."
    s.daily_plan_req = f"{s.name} now works as a {role_disp} in {world}. {sched}"
    s.currently = (f"{s.name} has just taken on the role of {role_disp} and is "
                   f"adjusting to the new duties: {sched}")


def write_md(persona, row):
    """Persist the persona's current state to its .md (role header + the 5
    identity sections + an Attributes section)."""
    s = persona.scratch
    name = s.name
    role = (row.get("role") if row else getattr(s, "role", "citizen")) or "citizen"
    role = role.replace("_", " ")
    fam = ((row.get("family_id", "").strip() if row else "") or "none")
    social = (row.get("social_class", "") if row else "")

    sec_vals = {"Personality": s.innate, "Background": s.learned,
                "Current Goals": s.currently, "Daily Routine": s.lifestyle,
                "Daily Plan": s.daily_plan_req}
    lines = [f"# {name}", "",
             f"**Role:** {role} | **Age:** {s.age} | "
             f"**Social Class:** {social} | **Family:** {fam}", "", "---", ""]
    for section in _MD_SECTIONS:
        lines += [f"## {section}", str(sec_vals.get(section, "") or ""), ""]
    lines += ["## Attributes"]
    if row:
        for k in _ATTR_KEYS:
            if row.get(k) not in (None, ""):
                lines += [f"- {k}: {row[k]}"]
    lines += [""]
    try:
        path = _md_path(name)
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        _last_mtime[name] = os.path.getmtime(path)   # don't re-apply our own write
    except Exception as e:
        logger.warning(f"[MD] write failed for {name}: {e}")


def reload_md(persona, row):
    """Re-seed a persona from its .md if the file changed since we last applied
    it. Returns True if anything was applied. Role edits in the header re-derive
    the role-driven identity fields; section/attribute edits apply directly."""
    name = persona.scratch.name
    path = _md_path(name)
    if not os.path.exists(path):
        return False
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return False
    if _last_mtime.get(name) == mtime:
        return False   # unchanged since last apply — leave the live state alone
    _last_mtime[name] = mtime

    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return False

    s = persona.scratch
    changed = False

    # Section edits (Personality/Background/Current Goals/Daily Routine/Daily Plan).
    for section, key in _MD_SECTIONS.items():
        m = re.search(rf'## {re.escape(section)}\s*\n(.*?)(?=\n##|\Z)',
                      content, re.DOTALL)
        if m:
            text = m.group(1).strip()
            if text and getattr(s, key, None) != text:
                setattr(s, key, text)
                changed = True

    # Attribute edits -> the CSV row (drives corruption/election/news).
    if row is not None:
        for line in content.splitlines():
            mm = re.match(r'\s*-\s*(\w+)\s*:\s*(.+)', line)
            if mm and mm.group(1) in _ATTR_KEYS:
                row[mm.group(1)] = mm.group(2).strip()
                changed = True

    # Role edit in the header re-derives lifestyle/currently/daily_plan from the
    # new role (overrides any stale section text for those fields).
    mr = re.search(r'\*\*Role:\*\*\s*([^|]+)', content)
    if mr:
        new_role = mr.group(1).strip().replace(" ", "_")
        if new_role and new_role != getattr(s, "role", None):
            apply_role(persona, row, new_role)
            changed = True

    if changed:
        logger.info(f"[MD] re-seeded {name} from edited .md")
    return changed


def reload_all(personas, agent_rows_by_name):
    """Re-seed every persona from its .md (mtime-gated). Called once per sim-day."""
    n = 0
    for name, persona in personas.items():
        try:
            if reload_md(persona, agent_rows_by_name.get(name)):
                n += 1
        except Exception as e:
            logger.warning(f"[MD] reload failed for {name}: {e}")
    if n:
        print(f"[MD] re-seeded {n} persona(s) from edited .md files", flush=True)
    return n
