#!/usr/bin/env python3
"""
analyze_election.py — read-only election-outcome reconstruction for a sim.

Compares each persona's LIVE role (autosaved scratch.json) against the
bootstrap CSV to answer: who holds each elected seat now, who was re-elected
vs replaced, and which families capture multiple seats. Safe to run against a
live sim (reads only).

Usage (on VM B, from backend_server):
  python analyze_election.py --sim sim_control_30d2 \
      --csv /home/student/197/barangay_agents_500_dynasty.csv
  python analyze_election.py --sim sim_antidynasty_30d2 \
      --csv /home/student/197/barangay_agents_500_dynasty_antidynasty.csv \
      --out /tmp/election_anti.csv
"""
import argparse
import csv
import json
import os

ELECTED = ["mayor", "vice_mayor", "councilor", "barangay_captain", "barangay_kagawad"]
STORAGE = os.environ.get(
    "SIM_STORAGE",
    "/home/student/197/generative_agents/environment/frontend_server/storage")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim", required=True)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out", help="optional CSV of seat holders")
    args = ap.parse_args()

    rows = {r["name"].strip(): r for r in csv.DictReader(open(args.csv))}
    base = os.path.join(STORAGE, args.sim, "personas")

    seats = {}          # position -> [(name, was_role, family)]
    for name in sorted(os.listdir(base)):
        sp = os.path.join(base, name, "bootstrap_memory", "scratch.json")
        try:
            with open(sp) as f:
                s = json.load(f)
        except Exception:
            continue
        role = s.get("role", "")
        if role in ELECTED:
            r = rows.get(name, {})
            seats.setdefault(role, []).append(
                (name, r.get("role", "?"), (r.get("family_id") or "").strip()))

    incumbents = newcomers = 0
    fam_seats = {}
    out_rows = []
    print(f"=== {args.sim} — elected seats (live roles vs bootstrap CSV) ===")
    for pos in ELECTED:
        for name, was, fam in sorted(seats.get(pos, [])):
            re_el = was == pos
            incumbents += re_el
            newcomers += not re_el
            if fam:
                fam_seats[fam] = fam_seats.get(fam, 0) + 1
            tag = "RE-ELECTED" if re_el else f"new (was {was})"
            print(f"  {pos:18s} {name:28s} {tag:24s} fam={fam or '-'}")
            out_rows.append({"position": pos, "name": name, "initial_role": was,
                             "re_elected": re_el, "family_id": fam})

    multi = {f: c for f, c in fam_seats.items() if c >= 2}
    dyn_bonus = sum((c - 1) * 0.05 for c in multi.values())
    print(f"\n  {incumbents} re-elected, {newcomers} new")
    print(f"  families with 2+ seats: {multi or 'none'}  "
          f"(dynasty seat-share diagnostic = {dyn_bonus:.2f})")

    if args.out:
        with open(args.out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
            w.writeheader()
            w.writerows(out_rows)
        print(f"  wrote {args.out}")


if __name__ == "__main__":
    main()
