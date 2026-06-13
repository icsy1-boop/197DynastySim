# Trial Data — DYNASTY.EXE 30-day run pair

Backed-up macro logs for the matched control vs. anti-dynasty trial, so the
record survives a VM reset. These are pulled from the VM B storage at
`storage/<sim>/reverie/`.

## Trial parameters
- **Population:** 500 agents, identical base population forked into both arms.
  - Control → `barangay_agents_500_dynasty.csv` (4 dynasties intact)
  - Anti-dynasty → `barangay_agents_500_dynasty_antidynasty.csv` (same population;
    surplus same-family officials demoted at bootstrap)
- **Horizon:** 30 sim-days = 720 steps (1 step = 1 sim-hour, 24 steps = 1 sim-day).
- **Election:** step 192 (sim-day 8). Campaign announced step 48; candidacy
  lock-in step 120; journalist surveys + candidate re-polls every 48 steps;
  weekly news broadcast every 168 steps; protest ticks every 72 steps while
  unrest >= 0.60.
- **Anti-dynasty rule:** at election winner-resolution, if a winner's family
  already holds a seat this cycle, the next highest vote-getter from a
  different family wins instead (no same-family sweep).

## Files
| File | Contents |
|------|----------|
| `corruption_log_control.csv` | Per-10-step macro history, control arm |
| `corruption_log_antidynasty.csv` | Per-10-step macro history, anti-dynasty arm |
| `world_metrics_*.json` | Final/live world-metric snapshot per arm |

CSV columns: `step, datetime, corruption_index, dynasty_bonus, welfare, unrest`
(all indices clamped to [0,1]). Snapshot captured at control step ~700 /
anti-dynasty step ~710 (essentially the full 720-step run).

## Headline result (see paper Results & Discussion)
Both arms sharply drop corruption at the step-192 election (memory-based voting
ejects corrupt incumbents). In **control** a new family (Salazar) re-consolidates
power, leaving `dynasty_bonus = 0.05`; in **anti-dynasty** the constraint blocks
same-family re-capture, holding `dynasty_bonus = 0.00`–`0.05` with no single
dominant family. Post-election the aggregate corruption/welfare/unrest series
of the two arms converge and cross, so the durable difference observed in this
single run pair is the family-concentration **structure**, not a sustained gap
in the aggregate indices.

## Caveats
- Single run per condition (LLM-stochastic) — not a statistical estimate.
- Anti-dynasty bootstrap demoted surplus officials but did not backfill the
  vacated seats, so the pre-election comparison is partially confounded by a
  smaller seated-official count; the post-election comparison (both fully
  seated) is the cleaner one.
