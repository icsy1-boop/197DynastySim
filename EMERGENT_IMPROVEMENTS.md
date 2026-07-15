# Emergent Sim Improvements — Memory-Based World, No Fixed Behavioral Values

> **STATUS (Jul 8, 2026): first implementation wave DONE and deployed to VM B.**
> Implemented: §2.1 (all-NOTHING tick logging), §2.2 victim/beneficiary
> memories, §2.3 proximity witnesses, §2.4 evidence-based watchdog exposure
> (spread via media access, no fixed probability/audience), §2.5 memory-based
> risk (watch flag removed from prompt), §2.6 role-conditioned opportunities,
> §3.1 embedding classifier + dedupe, §3.2 starvation warning + mass/version
> CSV columns, §3.3 per-agent satisfaction (welfare = mean of per-agent
> readout; unrest = aggrieved share), §4.1 per-agent protest crowd, §4.2
> memory-derived blame, §4.3 LLM protest text, §5 name_trust readout (used by
> vote fail-safe + blame), §6 parallel votes + ABSTAIN + unbiased fail-safes
> (election & survey), §7 journalist-memory bulletin + deterministic media
> access + relevance-scaled reception, §9.4 barangay_roles.py, §9.5
> inject_dynasty_memories call removed, §9.6 skip-on-embed-failure everywhere,
> §9.7 bounded newest-first scans + per-node classification cache.
> New module: `barangay_roles.py`. Changed: mechanics, official_decisions,
> unrest, election, news, survey, reverie.
> NOT yet done: §2.7 trait drift, §4.4 organizer decision, §6 vote
> checkpointing + embedding retrieval, §8 world events/economy/stances,
> §9.2 (log CSV keeps old columns on existing files; new sims get v2), §9.3
> log rotation, dashboard trust panel.
> **VALIDATION PASSED (Jul 8, 2026)** — `sim_valid_mem2` (fresh fork of
> base_control_500, 26 steps, DECISION_INTERVAL=12, saved at step 26):
> - Both [DECISION] ticks fired: 26/26 officials decided (tick 1: 1 corrupt/
>   1 exposed, 22 honest/4 amplified; tick 2: 4 corrupt/1 exposed, 16 honest/
>   6 amplified — evidence gate makes exposure conditional, not automatic).
> - Emergent scandal with real texture: Antonio Santiago (dynasty head) padded
>   the ResA road contract ("5% contingency"); a Salazar watchdog published it
>   with an LLM-written headline that reached the dashboard news queue.
> - mem2 CSV columns written; masses MOVED because of the decisions
>   (step 10 → 20: corr 203→6663, gov 1022→25225, corruption_index →0.209
>   target, welfare responded per-agent, dynasty_bonus exactly 0.35 = the four
>   control dynasties, no contractor artifact, no silent freeze).
> - Protest fired at step 24 with MEMORY-DERIVED blame naming the actual
>   culprits (Santiago + the tick-2 corrupt officials), rally text grounded in
>   the crowd's real grievances (the unrepaired poor-sector road), 60 marched.
> - Bonus emergence: dynasty members coordinating "discretion to protect the
>   family's reputation" in ordinary school conversations.
> - **CALIBRATION FINDING → FIXED (Jul 9):** thresholds were a red herring.
>   At th=6, 467/500 "aggrieved"; at th=10 still 496/500 — because the test
>   counted 0.5·corruption mass, i.e. KNOWLEDGE of corruption (witness/media
>   memories, per-agent mass ~55 after one media cycle), and because victim
>   memories carried a "corruption" keyword that mis-classified them as
>   corruption instead of grievance. Fixes: aggrieved = grievance-only;
>   victim/protest-participation memories classify as GRIEVANCE (kw excludes
>   "corruption"); protest hearers get poignancy 5 (< threshold) so protests
>   don't self-amplify from awareness. `UNREST_PERSONAL_TH` stays 6.0.
> - **CROSS-SIM CONTAMINATION BUG FOUND + FIXED (Jul 9):** the same run
>   exposed that `persona_md.py` used ONE global `personas/` dir for all sims
>   — a previous sim's election demotions re-seeded the fresh fork at its
>   first day boundary (mayor/captains silently became civil_servant_admin;
>   the parallel 30d research runs cross-contaminated each other the same
>   way). reverie now calls `set_md_dir(<sim_folder>/personas_md)` — per-sim
>   store, fresh forks start clean; `seed_md` writes an editable .md for all
>   500 agents at sim start (steering feature now covers everyone from step 0).
> - **RE-VALIDATION PASSED (`sim_valid_mem3`, Jul 10):** dynasty_bonus held
>   0.35 through the day boundary (the exact point the leak corrupted mem2);
>   aggrieved baseline 0.4% → 7.8% after one UNexposed corrupt act (≈ its ~30
>   real victims; old semantics: 43%) → 131 (26%) after five cumulative
>   corrupt acts — anger scales with actual harm, not media reach. Protest
>   marched 60 real victims, blame named the deciding officials. Bonus: with
>   19 honest acts amplified and corruption unexposed, corruption_index FELL
>   (0.148→0.139) and welfare rose — the recovery pathway moves the readout
>   both directions.
> - **Full 50-step soak (saved at 50, zero errors):** EMERGENT IMPUNITY
>   ESCALATION — corrupt acts per tick went 1→4→8→7 as officials' salient
>   memories filled with colleagues' UNpunished acts (0 exposures at tick 36);
>   deterrence runs in reverse exactly as theorized. Aggrieved growth stayed
>   victim-proportional throughout (39→131→260→311→361 of 500) and sublinear
>   as overlap saturated; blame stayed on the actual repeat offenders. NOTE
>   for research runs: this test ran decisions at 4× research cadence — 20
>   corrupt acts in 2 sim-days. If 30-day runs trend toward aggrieved
>   saturation anyway, the lever is `DECISION_VICTIMS` (30) or victim-memory
>   poignancy, NOT the threshold (the semantics are correct — every aggrieved
>   agent was actually harmed).

Goal: every world-level outcome (corruption, welfare, unrest, protests, news, votes)
is a READOUT of agent memories, and every action that changes the world is an
agent DECISION grounded in those memories. Fixed values that remain should be
operational pacing (intervals, worker caps, smoothing guardrails) — never
behavior (probabilities, random audiences, flat poignancies, keyword lists,
random blame).

Cost guardrail (4B on VM A is the bottleneck, ~22 tok/s under 2-sim load).
Prefer, in order:
1. **free** — heuristics over memory nodes already in RAM
2. **embed** — embedding calls (:8002, separate from the 4B, near-free)
3. **27B** — new LLM calls that don't need the abliterated model
4. **4B** — only corruption-core decisions

---

> **MID-RUN STATUS (Jul 14, day ~13 of 30, step ~320/720):** both v2 arms
> healthy, zero tracebacks, watchdog uptime 4 days. **The treatment effect is
> real and in the hypothesized direction** (`figures/metrics_v2_midrun.png`):
> corruption CROSSED OVER (~step 170) — control rising (0.35), anti falling
> (0.20); welfare diverged after the election (anti 0.63 vs control 0.55);
> control corr_mass ≈ 2.4× anti's. **Election (step 192):** control —
> dynasties adapted (Mark Santiago lost the mayorship but Antonio Santiago
> moved UP to captain; the David family now holds 3 seats; seat-share
> 0.35→0.15); anti — wholesale turnover (11/15 seats new), max-1-per-family
> enforced (0.00), and a COA auditor won vice-mayor. Observations for the NEXT
> run (no mid-run changes — comparability): (1) dynasty officials choose SPIN
> ~100%, PAY never — reword the influence prompt so patronage is equally
> salient, or gate PAY to pre-election windows; (2) unrest/aggrieved ceiling
> confirmed at research cadence (0.90/0.84 by day 13) — lower DECISION_VICTIMS
> or victim poignancy next time; grv_mass and protest counts still
> discriminate; (3) the influence machinery's "dynasty" gate
> (`_dynasty_families` = family with ≥2 members in the POPULATION) is too
> broad — nearly any blamed official qualifies, so both arms spin equally.
> Same rule both arms ⇒ comparison valid, but next run should gate on
> families holding ≥2 SEATS (true dynasties) so the counter-machinery is the
> dynasty-specific advantage it's meant to model.

## 0. Empirical findings from the completed 30d runs (motivation)

Pulled from VM B logs/CSVs (runs `sim_control_30d` / `sim_antidynasty_30d`,
finished at step 720):

- **`[DECISION]` never fired in either run** (zero occurrences in both logs).
  The runs launched before the Phase 2 deploy; the emergent-decision pathway
  produced none of the data. Everything below is downstream of fixing this.
- **Corruption froze silently**: control sat at exactly 0.5309 for the last
  ~110 steps — the "no signal yet" fallback in
  `barangay_mechanics.log_corruption_step` (no corruption/governance memories
  inside the 14-day window) repeats the previous value forever, no warning.
- **Arms indistinguishable**: control 0.5309 vs anti 0.5279 corruption;
  welfare 0.334 vs 0.374. No measurable treatment effect.
- **Anti arm shows `dynasty_bonus = 0.05`** (should be ~0): `POLITICAL_ROLES`
  in barangay_mechanics counts `contractor`, which the anti-dynasty rule does
  not govern.
- **Metric semantics changed mid-run** (early rows: old trait formula with
  dynasty_bonus 0.30 folded in; later rows: memory readout). The CSV mixes two
  incompatible formulas with no version marker.
- **`/tmp/sim_control_30d.log` is 38.5 GB.** Will fill the disk next run.

---

> **RESEARCH RUNS RELAUNCHED (Jul 10, 2026): `sim_control_30d2` +
> `sim_antidynasty_30d2`** on the fixed engine. Pre-launch sequence executed:
> (a) **dynasty influence machinery** added (`step_dynasty_influence` in
> barangay_official_decisions — SPIN fake news with lived-harm skepticism +
> watchdog fact-checks, PAY patronage/vote-buying with witness/exposure risk);
> (b) watchdog log rotation (4 GB cap; v1 logs reduced to 100 MB tails —
> freed 78 GB); (c) `base_antidynasty_500` re-bootstrapped from the backfilled
> CSV **with an isolated `--personas-dir`** (first attempt loaded 500 stale
> global .md files → identity-text contamination; barangay_init's default
> personas dir is the same global leak — always pass a fresh dir); (d) v1
> 30d runs archived (results compromised by the .md leak). Watchdog repointed
> to the v2 names.

1. Validate the decision module end-to-end on `sim_control_500` (§2.1)
2. Embedding classifier + mass logging + starvation warning (§3.1, §3.2)
3. Victim/beneficiary memories (§2.2)
4. Evidence-based exposure via watchdogs (§2.4)
5. Per-agent protest participation + memory-derived blame (§4)
6. Dynamic per-agent satisfaction (§3.3) + per-official trust readout (§5)
7. Election: parallel voting, memory turnout, embedding retrieval (§6)
8. News from the journalist's memory stream (§7)
9. Housekeeping/robustness (§9)
10. Longer-horizon ideas (§8)

---

## 2. Official decisions (`barangay_official_decisions.py`)

### 2.1 Activate + validate (BLOCKER)
The module is wired in reverie.py but has never run in a real sim. On
`sim_control_500` (the testing ground, NOT the research runs): run ~100 steps,
confirm `[DECISION]` ticks fire, acts appear as memories, metrics move.
Add a per-tick summary print even when all officials chose NOTHING
(currently `if n_corrupt or n_honest` hides an all-NOTHING tick from the log —
indistinguishable from the module not running).

### 2.2 Victim / beneficiary memories (highest realism payoff)
Today a CORRUPT act creates witness memories in 40 random agents but harms
no one. Give each `_OPPORTUNITIES` entry an `affected_group` selector
(sector, role, or condition — e.g. road repair → poor-sector residents;
relief funds → flood-affected families; permit bribe → the specific applicant):

- CORRUPT → inject deprivation memories into the affected group
  ("the road in our sector was never fixed", "we never received the relief").
- HONEST → inject benefit memories into the same group
  ("the relief goods arrived", "the road got fixed").

Grievance then originates from lived deprivation, localized by sector, and
welfare/unrest/votes/protests inherit that locality for free. Cost: free
(templated text + one embed per unique string).

### 2.3 Witnesses by proximity and ties, not `random.sample`
Select witnesses from: agents whose `living_area`/`work_zone` is near the
official's work_zone, co-workers, family, and recent conversation partners
(seq_chat). Uniform sampling makes spread structureless and flattens the
neighborhood/class dynamics the register system was built to express.
Cost: free.

### 2.4 Exposure = watchdog decision with an evidence chain
Remove `DECISION_EXPOSE_CHANCE=0.45`. Instead:
- A watchdog can only expose what it *holds*: it was in the witness sample, or
  a witness told it in conversation (the organic path), or an auditor tick
  reviewed the official's office.
- Publishing is the watchdog's own LLM decision (27B is fine — journalists
  aren't corruption-core), fed by their salient memories (past retaliation,
  editor pressure, how many independent witnesses confirmed).
- Publication goes through the NEWS system (bulletin + conversation spread),
  NOT direct injection into `DECISION_EXPOSE_AUDIENCE=200` random agents.
  Direct wide injection makes the corruption metric partially measure the
  injection audience size — circular.

### 2.5 Risk perceived from the official's own memories
`watchers_active` is a binary "any watchdog exists" (always true), election
proximity a fixed 30-day band. Drop the hardcoded watch line from the prompt:
a colleague exposed last week already sits in the official's salient memories
(`converse._salient_memories`), so deterrence emerges organically. Keep only
factual context (days to election) if anything.

### 2.6 Opportunities from world state, not `random.choice` over 8 templates
- Minimum: condition on role (treasurer → invoices; captain → relief;
  procurement officer → bids).
- Better: world events (§8.1) open opportunity windows (budget release,
  typhoon relief), and resident complaints in the memory stream (a stuck-permit
  conversation) spawn the matching temptation for the responsible official.

### 2.7 Trait drift (longer-term)
Traits are static numbers injected into every prompt — themselves a fixed
value driving behavior. Options: (a) erode/raise integrity slightly after
each CORRUPT/HONEST act; (b) drop numeric traits from the prompt after the
first weeks and rely on the agent's own memory of past acts + ISS (their
history *is* their character). Validate on the testing ground first — this
changes decision distributions.

---

## 3. World metrics (`barangay_mechanics.py`)

### 3.1 Embedding classifier instead of keyword lists
`_CLASS_KW` / `_CLASS_TEXT` miss Taglish conversation memories and any LLM
phrasing not on the list — a likely contributor to end-of-run signal
starvation. Every node already stores an embedding; classify by cosine
similarity to 3–5 anchor texts per class (corruption / governance /
grievance), threshold ~0.5–0.6, tuned once on the testing ground. Anchor
embeddings computed once at startup. Cost: free at readout time (embeddings
already exist); keyword hits can remain as a fast pre-pass.

Also **dedupe identical descriptions** when massing: 200 injected copies of
one scandal should count reach (distinct agents holding it), organic chat
mutations count extra — so the metric measures spread, not injection count.

### 3.2 Starvation warning + mass logging
- When `corr + gov < eps`, print `[METRICS] no corruption/governance signal
  in window` instead of silently freezing. Would have caught the flatline.
- Log the raw masses as CSV columns (`corr_mass, gov_mass, grv_mass`) next to
  the indices — the thesis can then show the *mechanism*, and debugging gets a
  direct view of what the classifier sees. Keep existing columns so the
  dashboard parser still works (append new columns at the end).

### 3.3 Dynamic per-agent satisfaction (kill the static CSV column)
`base_welfare` reads bootstrap `satisfaction` forever — welfare is anchored to
a constant. Replace with a per-agent readout: balance of that agent's own
positive (service/relief/benefit) vs negative (deprivation/grievance) memories
in the window, mapped onto their bootstrap value as a prior. Gives per-sector
welfare (poor sectors degrade first) and localized unrest for free.
Alternative/complement: reuse `barangay_survey.py` to micro-poll a rotating
sample ("how satisfied are you, 0–10", fed by salient memories) — 27B, cheap,
and doubles as thesis data.

### 3.4 Formula weights
The linear weights (0.45/0.30/0.35, 0.55/0.45) are calibration, acceptable as
documented constants — but once §3.3 exists, prefer welfare as the **mean of
per-agent welfare** (a true population statistic) over a formula, and unrest
as the **share of agents above a personal grievance threshold**. Keep the
smoothing (`WELFARE_RATE`) as a stability guardrail.

---

## 4. Protests (`barangay_unrest.py`)

### 4.1 Participation from each agent's own grievance mass
Replace the fixed global gate (`unrest ≥ 0.60` → always 250 hear / 60 random
march) with a per-agent readout: score each resident's own grievance memories
(same classifier as §3.1, per-agent); those above a personal threshold are the
crowd. Crowd size becomes a *measurement* (and a great thesis plot), not a
parameter. Keep a cap only as a perf guardrail.

### 4.2 Blame from memories, not `random.sample(incumbents, 3)`
Currently innocent officials get named in poignancy-8 protest memories that
feed voting — this actively corrupts the causal chain. Blame = the officials
most frequently appearing in the population's corruption/scandal memories
(count subject mentions in classified nodes). Cost: free.

### 4.3 LLM protest text from actual grievances
One 27B call: given the top-k grievance memory descriptions, write the chant /
placard line, so the rally names the actual ghost project. Fallback to the
template on LLM failure.

### 4.4 Organizer decision (optional, nice)
Instead of an interval check, a CSO organizer / aggrieved resident with high
personal grievance decides (LLM, 27B) whether to call a rally, where, and
against whom — venue can then vary (municipal hall, the official's office)
instead of the fixed plaza. Keep the interval as a max-frequency guardrail.

---

## 5. Per-(agent, official) trust readout — one mechanism, four consumers

A cheap function: for agent A and official O, sum
`sign · poignancy · recency_decay` over A's nodes mentioning O (sign from the
§3.1 class: corruption/grievance negative, governance positive). Cache per
metrics tick. Use it for:

1. **Vote fail-safe** — replaces "family member, else first candidate in the
   list" (first-candidate bias when the LLM fails).
2. **Protest blame targets** (§4.2 is the population aggregate of this).
3. **Survey answers** — poll fail-safe becomes trust-weighted instead of
   fail_safe-name.
4. **Conversation stance hint** — optional line in the whole-chat prompt
   ("you deeply distrust Mayor Santiago") when |trust| is extreme.

Also: expose per-official trust in the dashboard (roadmap item), and log the
top-5 most-distrusted officials per metrics tick.

---

## 6. Election (`barangay_election.py`)

- **Parallelize `collect_votes`** — currently serial: ~400 voters × 5
  positions of LLM calls in a Python loop. Use the same ThreadPoolExecutor
  pattern as candidacy polling. (Robustness: election step otherwise takes
  hours and a mid-election crash loses everything — also checkpoint votes to
  disk per position.)
- **Embedding retrieval for candidate memories** — substring-on-name misses
  "the mayor's scandal" and Taglish references. Retrieve by embedding
  similarity to "candidate name + role", keep name substring as a pre-pass.
- **Memory-driven turnout** — everyone votes today (100% turnout). Let
  disillusioned agents abstain and angry ones show up: turnout from personal
  grievance/efficacy readout, or a one-line addition to the vote prompt
  allowing ABSTAIN. Turnout differential is a real dynasty-literature effect,
  nearly free to add, and a strong thesis metric.
- **Vote memory poignancy** — flat 4; scale by how contested/emotional the
  vote was (had scandal memories about a candidate → higher).

---

## 7. News (`barangay_news.py`)

- **Bulletin from the journalist's memory stream**, not `world_metrics`
  numbers. Feeding the metric into the narrative that feeds the metric is a
  feedback shortcut. Give the bulletin LLM the journalist's salient memories
  (what they witnessed/exposed/heard) + queued publishable stories from §2.4.
  27B call, same cost as today.
- **Reception poignancy by personal relevance** — flat 8/6/4 per access level
  today. Scale up when the recipient already holds related grievance memories
  (embedding similarity of bulletin vs their recent nodes — cheap since both
  embeddings exist); a scandal bulletin should hit an already-aggrieved
  resident harder.
- **Deterministic media access** — replace the 40% random radio roll with a
  deterministic rule from the row (e.g. education≥2 AND not lowest class), so
  the two arms don't differ by RNG in who hears news.

---

## 8. Longer-horizon ideas

### 8.1 World events (roadmap item)
Periodic exogenous events — budget release, typhoon → relief window, fiesta —
that (a) open decision opportunities (§2.6), (b) create direct experience
memories in affected sectors, (c) give the news something exogenous to report.
This makes the two arms diverge through *responses to shared shocks*, which is
a clean comparison.

### 8.2 Light economic layer
Relief/projects as concrete goods: a corrupt relief decision means specific
families *didn't get* goods (memory: "we got nothing"), an honest one means
they did. Welfare then aggregates real receipt/deprivation events instead of
abstract indices. §2.2 is the minimal version; this extends it to quantities
and repeated deliveries.

### 8.3 Conversation stance extraction
Chats already spread memories; optionally extract commitments from chat
summaries ("agreed to join the rally", "will vote for X") as tagged memories
(embed-classified, no extra LLM call) so social influence is measurable.

### 8.4 Reflection-driven politics
Officials' and residents' reflections (already in the framework) could be
seeded with political questions near elections ("who deserves my vote?") so
the reflection tree itself produces voting-relevant thoughts — currently
reflection topics are generic.

### 8.5 Sprite tinting by trust/family/role (dashboard, roadmap item)
Visualize §5 trust or grievance per agent on the map — makes the emergent
spatial pattern (aggrieved poor sector) visible in the replay.

### 8.6 Scenario packs — the sim beyond political dynasties
The .md-as-source-of-truth store is now per-sim and seeded for every agent at
step 0 (`storage/<sim>/personas_md/`), so a scenario is just: fork a base +
edit the .md files (roles, goals, attributes). To make NON-political
experiments first-class, the remaining hardcoded scenario surface should
become configurable per run:
- **Opportunity list** (`_OPPORTUNITIES` in barangay_official_decisions) —
  load from a JSON/YAML file (`DECISION_OPPORTUNITIES_FILE`) so a disaster-
  response or market-economy scenario presents different dilemmas.
- **Classifier anchors + keyword sets** (`_ANCHOR_TEXTS`/`_CLASS_KW` in
  barangay_mechanics) — per-scenario metric definitions (e.g. classify
  "hoarding/price-gouging vs fair-trade vs scarcity-grievance" instead of
  corruption/governance/grievance).
- **Role sets** (barangay_roles) — who "decides", who "watches", who is
  exempt from protests.
With those three files swappable, the same engine (memory readout → decisions
→ victims → exposure → collective action → votes) runs any community dynamic.

---

## 9. Robustness / housekeeping (do regardless)

1. **Metric starvation warning** (§3.2) — never freeze silently.
2. **Version-stamp `corruption_log.csv`** — add a `formula_version` column (or
   start a new file on deploy) so a mid-run code change can't silently mix
   semantics again.
3. **Log rotation** — `/tmp/sim_*.log` hit 38.5 GB. Pipe through
   `rotatelogs`/`split -b`, or at least gzip + truncate in the watchdog; keep
   `grep -a` compatibility.
4. **Unify role sets** — `OFFICIAL_ROLES`/`POLITICAL_ROLES` differ across
   barangay_mechanics (includes `contractor` → anti arm shows dynasty_bonus
   0.05), barangay_unrest (omits treasurer/secretary), decisions, election.
   One shared constant module (e.g. `barangay_roles.py`).
5. **Fix `inject_dynasty_memories` stale `thought_poignancy` kwarg** (known
   bug: injects 0, spams logs) — or remove the call; bootstrap already seeds
   family trust.
6. **Embedding failure fallbacks** — `[0.0]*384` in mechanics vs `[0.0]*768`
   elsewhere; zero vectors poison cosine retrieval. On failure: retry once,
   then SKIP the injection (log it), never store a zero vector.
7. **`_memory_masses` cost is unbounded** — scans every node of every persona
   every 10 steps. Keep incremental per-class tallies updated at
   node-creation time, or index nodes by creation date so the 14-day window
   scan is bounded. (With §2.2's wider injection this matters more.)
8. **All-NOTHING decision ticks must log** (§2.1).
9. **Election checkpointing** (§6) — persist per-position vote counts as they
   complete.
10. **Wide-injection memory bloat** — 200-agent audiences every 48 steps grow
    every stream and slow retrieval; with §2.4 (spread via news/conversation)
    direct wide injection mostly disappears. Until then, respect the 30-day
    expiration in retrieval paths.

---

## 10. QOL / UI / tooling improvements

### Dashboard & replay (frontend)
- ✅ **DONE (Jul 2026):** mem2 formulas on the panel, raw Memory Mass row
  (corr/gov/grv), Aggrieved Share metric, `sim_metrics` returns the new fields.
- ✅ **Metric sparklines (Jul 10)** — `sim_metrics` returns `history:
  [[step, corr, welfare, unrest], ...]` (thinned ≤100 points); neutral SVG
  trend line under each of the three index bars. NOTE: the Django dev servers
  do NOT autoreload views.py — restart the django tmux sessions after a
  frontend deploy (the watchdog recreates them if killed).
- **Event markers on the scrubber** — persist protest/scandal/election steps
  into `world_metrics.json` (`event_steps: {step: label}`) and draw ticks on
  the jump-to-step slider; click a tick to jump to the drama. Best replay QOL
  win for demos.
- **Agent inspector upgrades** — the right slide-out panel already shows the
  clicked agent; add their top salient memories, their grievance/governance
  mass, and their `name_trust` toward the current officials (one endpoint call
  computing it on demand). Turns "why did this agent vote that way?" into a
  click instead of a storage dig.
- **Per-official trust table** — small panel section ranking seated officials
  by population trust (aggregate `name_trust`); updates each metrics tick.
  This is the dashboard face of the §5 readout and a direct thesis figure.
- **Sector welfare tint** — per-agent satisfaction is now computed; average it
  by home_zone and tint sector overlays green↔red. Makes "the poor sector is
  suffering first" visible on the map itself.
- **Sprite affordances** — officials get a small badge; ✊ already marks
  protesters; tint officials by live trust (roadmap item).

### Ops / tooling (VM)
- **Log rotation (§9.3, still open)** — add a size check to `sim_watchdog.sh`
  (runs every 5 min): if `/tmp/sim_*.log` > 4 GB, keep the last ~100 MB and
  `truncate -s 0` (append-mode `tee -a` handles truncation safely). The 30d
  control log hit 38.5 GB.
- **`run_valid.sh` wrapper** — one-liner validation launcher (fresh fork,
  compressed `DECISION_INTERVAL`, auto-named sim + tmux session) so feature
  tests don't require remembering the env recipe.
- ✅ **`plot_metrics.py` (Jul 10, repo root)** — matplotlib, reads N
  `corruption_log.csv` files (both v1 and mem2 formats) → 4 index panels
  (control vs anti overlay, validated blue/orange palette) + per-run memory-
  mass panels (direct-labeled class trio). Smoke-tested on the v1 archives:
  `figures/metrics_v1_archive.png` — the dynasty panel visibly shows the .md
  contamination (anti arm jumps 0.00→0.30 at step ~30), a ready-made "before"
  exhibit for the thesis.

### Analysis artifacts (cheap to add, thesis gold)
- **Decision audit CSV** — append every official decision to
  `reverie/decisions.csv` (`step, name, role, opportunity, decision, exposed,
  witnesses, victims`). The full causal chain (decision → memories → metrics →
  votes) becomes reconstructable without grepping a 40 GB log.
- **Election artifact** — `collect_votes` dumps
  `reverie/election_<step>.csv` (position, candidate, votes, abstentions) +
  per-voter choices. Enables turnout/loyalty analysis and the
  "corrupt-officials re-elected vs replaced" table.
- **Protest roster** — log who marched (they're now individually meaningful:
  each marcher is personally aggrieved) → grievance-to-participation curves.

## 11. Dynasty power & family loyalty (v3 — IMPLEMENTED, staged for post-720 deploy)

How does a dynastic family actually CONTROL power, and why do people stay
loyal? Not (mainly) fraud — **personal debt**. The v3 wave makes the
patron-client machine a first-class, memory-mediated mechanic. All code is
written, compiled, and STAGED locally; it deploys to VM B only after the v2
runs hit step 720, so a watchdog restart cannot change behavior mid-experiment.

### 11.1 What was implemented (this wave)

- **`barangay_patronage.py` (NEW) — utang na loob as memory.**
  - `seed_patronage`: one-time (marker-guarded) at fresh-sim start. Every
    family holding **2+ seats** gets a client base (`CLIENTS_PER_DYNASTY` 40):
    poor residents, neighbors of the family's officials first, each carrying a
    personal-debt memory toward the family's most senior official ("paid the
    hospital bill when nobody else would…"), **poignancy scaled by the
    client's own `family_loyalty` trait** (4–8), 90-day expiration — debts
    outlive news. Classified governance → feeds `name_trust` → votes.
  - `step_patronage`: every `PATRONAGE_INTERVAL` (96) steps, each dynasty
    official **LLM-decides (Tier-1) whether to spend on the machine**. GRANT →
    `PATRONAGE_FAVORS` (8) clients get fresh favor memories (debt renewed); a
    few observers read the same act as machine politics (corruption-classified,
    low poignancy). Decline → the debt decays with the memory halflife —
    **neglected clients drift**. Loyalty is emergent and contestable.
- **MOBILIZE — the liders.** Third option in the influence machinery (now
  SPIN | PAY | MOBILIZE | NOTHING): send ward leaders door-to-door; everyone
  whose OWN memories already trust the official (clients, beneficiaries, kin;
  top `MOBILIZE_REACH` 60 by name_trust) receives a loyalty-reminder memory
  that surfaces in vote retrieval. Gratitude, activated at the ballot box.
- **Seats-based dynasty gate.** The machine (influence + patronage) belongs to
  families holding **≥2 live seats** — replacing the family-size gate that let
  any blamed official spin. In the anti arm no family qualifies, so the
  counter-machinery itself is part of the treatment, as it should be.
- **PAY made salient** in the influence prompt (ayuda framed as customary and
  effective, not as a crime) — addressing the observed all-SPIN behavior.
- **Loyalty-scaled bloc voting.** The family-candidate vote fail-safe now
  applies only to voters whose own `family_loyalty` ≥ 0.5 — a low-loyalty
  relative votes their memories like anyone else. Defection becomes possible.

The full loop this creates: favors → gratitude memories → name_trust → votes
AND mobilization; scandals → grievance in the SAME memory streams; the client
who received rice AND lost relief money to the same family holds both memories,
and the ballot decision emerges from whichever weighs more. Spin cannot touch
lived gratitude or lived harm — only favors and harms can.

### 11.1b Loop-gain experiments — both closed loops are now fully adjustable

Each loop has three independent dimensions, all env-tunable per run:

| Dimension | Loyalty loop | Grievance loop |
|---|---|---|
| **Depth (gain)** — how hard each memory hits | `LOYALTY_GAIN` (1.0) — scales utang seeds (5+3·loyalty), favors (7), mobilize reminders (6); clamp [1,9] | `GRIEVANCE_GAIN` (1.0) — scales victim deprivation (8) + protest participation (8); clamp [1,9] |
| **Width** — how many people touched | `CLIENTS_PER_DYNASTY` (40), `PATRONAGE_FAVORS` (8), `MOBILIZE_REACH` (60), `PATRONAGE_RECIPIENTS` (30) | `DECISION_VICTIMS` (30), `PROTEST_AUDIENCE` (250), `DECISION_WITNESSES` (40) |
| **Persistence** — how long it lasts | `PATRONAGE_EXPIRE_DAYS` (90) | 30-day expiry; both loops share `METRIC_MEM_HALFLIFE_H` (168) / `_WINDOW_H` (336) |

Thresholds act as inverse gains on loop OUTPUT: `UNREST_PERSONAL_TH` (6.0,
grievance→protest) and `SPIN_SKEPTIC_MASS` (6.0, grievance→spin-resistance).

**Sweep recipe** (short runs, e.g. 30-step forks of a base with a compressed
`DECISION_INTERVAL`): grid `LOYALTY_GAIN × GRIEVANCE_GAIN ∈ {0.5, 1.0, 1.5}²`,
one wrapper per cell exporting the pair, same seed base. Compare per cell:
dynasty vote share + re-election rate (analyze_election.py), client-base
retention (do utang memories out-mass grievance in clients' streams?),
protest count/size, corruption-index equilibrium. Hypothesis surface: at what
gain ratio does lived harm break utang na loob?

**Caveats for clean sweeps:** (1) gains apply at INJECTION — they affect new
memories only, so set them at launch, never mid-run; (2) keep both arms of any
control/anti pair at identical gains; (3) `GRIEVANCE_GAIN` deliberately does
NOT scale protest HEARERS (fixed 5) or media scandal (9) — those are awareness
channels; scaling them re-opens the self-amplification failure mode fixed in
mem2 calibration; (4) gain > ~1.15 saturates poignancy-8 injections at the
cap of 9 — for stronger effects widen the loop instead (width knobs).

### 11.2 What else can be improved (dynasty dynamics, future waves)

- **Compadrazgo (godparenthood) ties** — seed kin-like bonds between dynasty
  officials and selected non-family households (bootstrap or runtime): a
  second loyalty web wider than family_id, weaker than utang na loob.
- **Employment dependence** — agents whose work_zone is dynasty-controlled
  (family businesses, hall jobs) carry "my livelihood depends on their
  goodwill" memories: loyalty with a fear component; crossing the family has
  a personal cost. Feeds abstention as much as support.
- **Succession / bench strategy** — at campaign announcement, non-official
  dynasty adults receive "the family expects you to carry the name" memories
  (poignancy ∝ ambition × family_loyalty) → dynasty candidacies EMERGE when a
  seat is threatened (the Antonio-moves-up pattern, but planned).
- **Client defection dynamics** — when a patron's corruption VICTIM is also
  their client, inject a dissonance thought ("after everything they gave us —
  but it was our road money"). Track client-base churn as a metric: how much
  harm breaks utang na loob? That's a thesis question in itself.
- **Opposition coalitions** — aggrieved non-dynasty candidates could pool
  support (endorsement memories to each other's sympathizers) instead of
  splitting the anti-dynasty vote — the classic reason dynasties win
  pluralities.
- **Term limits + benchwarming** (RA 9164's 3-term rule): force rotation and
  watch dynasties cycle the seat through spouses/children — the real-world
  workaround the anti-dynasty bill targets.
- **Lider agents** — promote a few high-loyalty clients per dynasty into
  named ward leaders whose daily plans include making rounds; mobilization
  then happens through conversation (fully organic) instead of injection.
- **Deliberately excluded**: intimidation/red-tagging of journalists and
  organizers — real but heavy; revisit only with explicit sign-off.

### 11.3 Consolidated change log (all waves, for the thesis methods section)

1. **mem2 (Jul 8–9)** — metrics = memory readout (embedding classifier, per-
   agent satisfaction, aggrieved share); emergent decisions with victims,
   tie-based witnesses, evidence-gated exposure; per-agent protests with
   memory-derived blame; parallel election with ABSTAIN + trust fail-safes;
   journalist-memory news; zero-vector fix; `barangay_roles.py`.
2. **Isolation fixes (Jul 9–10)** — per-sim `personas_md` store (+ seed_md for
   all agents); grievance-only aggrieved semantics; `--personas-dir` bootstrap
   gotcha; log rotation; validated on `sim_valid_mem3` (impunity escalation
   observed).
3. **Influence v1 (Jul 10)** — SPIN fake news with lived-harm skepticism +
   watchdog fact-checks; PAY vote-buying with witness/exposure risk.
4. **v2 research runs (Jul 10–)** — clean bases, staggered launch, watchdog +
   rotation, hourly heartbeat; mid-run: corruption crossover, welfare
   divergence, dynasty adaptation vs turnover at the election.
5. **v3 loyalty wave (Jul 15, staged)** — this section.

## 12. Roadmap — v4 / v5 / v6

Sequenced so each wave has one theme, one validation run, and one experiment
it unlocks. (v1 = original macro events; v2 = mem2 emergent core; v3 =
loyalty machine, staged.)

### v4 — "The dynasty deepens" (political economy of loyalty)
Theme: richer dynasty power that can also be BROKEN realistically.
Unlocks: the loop-gain sweep program (§11.1b) + client-churn analysis.
- **Compadrazgo ties** — godparent bonds between dynasty officials and
  non-kin households; a second, weaker loyalty web beyond family_id.
- **Employment dependence** — dynasty-controlled work_zones ⇒ "my livelihood
  depends on their goodwill" memories; fear-loyalty that feeds ABSTENTION as
  much as support (turnout suppression, measurable).
- **Succession / bench strategy + term limits** (RA 9164 3-term rule) — the
  family fields spouses/children when a seat is threatened or termed out;
  "the family expects you to carry the name" memories (∝ ambition ×
  family_loyalty) at campaign announcement. Requires multi-election runs.
- **Client defection dynamics + churn metric** — when a patron's corruption
  VICTIM is also their client, inject the dissonance thought; log client-base
  retention per dynasty per tick. The thesis question: how much lived harm
  breaks utang na loob? (pairs with the gain sweep).
- **Opposition coalitions** — aggrieved non-dynasty candidates pool
  endorsements instead of splitting the vote; the classic reason dynasties
  win pluralities becomes testable.
- **Lider agents** — promote 2-3 high-loyalty clients per dynasty into named
  ward leaders whose daily plans include making rounds; MOBILIZE then flows
  through conversation (fully organic) instead of injection.
- Analysis artifacts if not landed earlier: decision audit CSV, per-voter
  election dump, protest roster (§10).

### v5 — "The world pushes back" (events, economy, scenarios)
Theme: exogenous pressure + a real goods layer + generalization.
Unlocks: shock-response comparison (arms diverge through shared shocks) and
non-dynasty experiments.
- **World events** — typhoon → relief window, budget release, fiesta season:
  each opens role-conditioned opportunities, creates direct experience
  memories in affected sectors, and gives news something exogenous.
- **Light goods economy** — relief as quantities with receipt/deprivation
  ledgers; welfare aggregates REAL receipt events; corruption becomes
  materially traceable (who didn't get the sacks of rice, exactly).
- **Scenario packs** — `DECISION_OPPORTUNITIES_FILE` + classifier-anchor +
  role-set configs per run (§8.6): disaster response, market/price-gouging,
  land disputes on the same engine.
- **Visualization of the loops** — per-official trust panel, sector welfare
  tint, sprite tinting by trust/loyalty; protest/scandal markers on the
  replay scrubber (§10).

### v6 — "Minds that change" (cognition & scale)
Theme: agents whose character moves; the sim at full size.
Unlocks: long-horizon studies (2-3 election cycles, 1000 agents).
- **Trait drift** — integrity erodes when corruption goes unpunished /
  hardens after exposure; formalizes the OBSERVED impunity escalation
  (1→4→8 corrupt acts/tick when watchdogs missed) into persistent character.
- **Reflection-driven politics** — politically seeded reflection near
  elections ("who deserves my vote?") so the reflection tree itself produces
  voting-relevant thought chains.
- **Conversation stance extraction** — commitments ("I'll join the rally",
  "we're voting for X") become tagged memories; social influence measurable.
- **Embedding retrieval for candidate memories** in voting (role/nickname
  references count, not just name substrings).
- **Perf for scale** — incremental memory-mass tallies, then the 1000-agent
  CSV (`barangay_agents_qc_1000_final-1.csv`) and month+ runs with 2-3
  election cycles (needed by v4 term limits anyway).

## 13. What stays fixed (deliberately)

- Interval knobs (`DECISION_INTERVAL`, `PROTEST_INTERVAL`, news cadence) —
  pacing/perf guardrails, env-tunable.
- Worker caps (`DECISION_MAX_WORKERS`, `MOVE_MAX_WORKERS`), token caps.
- Metric smoothing rates (`WELFARE_RATE`, `UNREST_RATE`) — stability, not
  behavior.
- Election law constants (seats, voting age, RA 9164 timeline) — the
  institutional rules being studied, correctly exogenous.
