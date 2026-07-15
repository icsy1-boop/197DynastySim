"""
antidynasty_gen.py — derive anti-dynasty CSV from a base CSV.

Enforces: no family_id may hold more than 1 OFFICIAL_ROLE seat. Surplus
same-family officials are demoted to civil_servant_admin AND each vacated seat
is BACKFILLED by promoting a non-dynasty agent (from a family that holds no
office) into that exact role.

Why backfill: leaving seats vacant gave the anti-dynasty arm fewer seated
officials than control, confounding the corruption comparison (the index
averages over seated officials). Backfilling keeps the official COUNT identical
to control; the replacement is chosen as the trait-CLOSEST eligible agent so the
official greed/integrity distribution stays matched too. The only thing that
differs between the arms is the dynasty STRUCTURE — a clean counterfactual.

Usage:
    python antidynasty_gen.py --input <csv> --output <csv>
"""
import csv, argparse, collections

OFFICIAL_ROLES = {
    'mayor', 'vice_mayor', 'councilor',
    'barangay_captain', 'barangay_kagawad', 'barangay_treasurer', 'barangay_secretary',
    'municipal_engineer', 'municipal_budget_officer', 'municipal_treasurer',
    'procurement_officer', 'business_permit_officer', 'disaster_officer',
    'social_welfare_officer',
}

# Senior offices want a more credentialed replacement; barangay-level/admin
# seats are filled across classes in the source data, so their floor is lower.
SENIOR_ROLES = {
    'mayor', 'vice_mayor', 'councilor', 'barangay_captain',
    'municipal_engineer', 'municipal_budget_officer', 'municipal_treasurer',
    'procurement_officer', 'business_permit_officer',
}

DEMOTION_ROLE = 'civil_servant_admin'


def _f(v, default=0.5):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _alive(row):
    return str(row.get('is_alive', '1')).strip().lower() not in ('0', 'false', 'no', '')


def _eligible_pool(rows, family_office, role):
    """Agents who could plausibly take `role`: adult, alive, not a student,
    not already an officeholder, from a family that holds no office, and
    minimally credentialed for the seat's seniority."""
    edu_floor = 4 if role in SENIOR_ROLES else 3
    pool = []
    for r in rows:
        if r['role'] in OFFICIAL_ROLES:        # already (or still) an official
            continue
        if r['role'] == 'student':
            continue
        if not _alive(r):
            continue
        age = _f(r.get('age'), 0)
        if age < 25 or age > 75:
            continue
        if family_office[r['family_id']] > 0:  # would create a new dynasty
            continue
        if _f(r.get('education_level'), 0) < edu_floor:
            continue
        pool.append(r)
    return pool


def generate(input_path, output_path):
    with open(input_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    by_id = {id(r): r for r in rows}
    family_office = collections.defaultdict(int)   # families currently holding a seat

    # --- Pass 1: keep the first official per family, collect surplus seats ---
    vacated = []   # list of demoted official rows whose seat must be refilled
    for row in rows:
        if row['role'] in OFFICIAL_ROLES:
            fam = row['family_id']
            if family_office[fam] >= 1:
                vacated.append({
                    'role': row['role'],
                    'integrity': _f(row.get('integrity')),
                    'greed': _f(row.get('greed')),
                    'work_zone': row.get('work_zone', ''),
                    'family': fam,
                })
                row['role'] = DEMOTION_ROLE      # demote the surplus member
            else:
                family_office[fam] += 1

    # --- Pass 2: backfill each vacated seat with a trait-closest outsider ---
    promoted = []
    chosen = set()
    for seat in vacated:
        pool = [r for r in _eligible_pool(rows, family_office, seat['role'])
                if id(r) not in chosen]
        if not pool:   # relax the education floor if nobody qualifies
            pool = [r for r in rows
                    if r['role'] not in OFFICIAL_ROLES and r['role'] != 'student'
                    and _alive(r) and 25 <= _f(r.get('age'), 0) <= 75
                    and family_office[r['family_id']] == 0 and id(r) not in chosen]
        if not pool:
            print(f"  WARN: no replacement available for {seat['role']} (left vacant)")
            continue
        # Pick the agent whose greed/integrity is closest to the demoted official.
        best = min(pool, key=lambda r: abs(_f(r.get('greed')) - seat['greed'])
                                      + abs(_f(r.get('integrity')) - seat['integrity']))
        promoted.append((best['name'], best['role'], seat['role'], best['family_id']))
        best['role'] = seat['role']
        if seat['work_zone']:
            best['work_zone'] = seat['work_zone']   # seat them at the right office
        family_office[best['family_id']] += 1
        chosen.add(id(best))

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    officials_after = sum(1 for r in rows if r['role'] in OFFICIAL_ROLES)
    officials_before = sum(1 for r in rows if r['role'] in OFFICIAL_ROLES) + len(vacated) - len(promoted)
    print(f"Input:    {len(rows)} agents")
    print(f"Demoted:  {len(vacated)} surplus same-family officials -> {DEMOTION_ROLE}")
    print(f"Promoted: {len(promoted)} non-dynasty replacements into vacated seats")
    for name, old, new, fam in promoted:
        print(f"    {name:28s} {old:22s} -> {new:22s} (fam {fam})")
    print(f"Officials seated: {officials_after}  (families with a seat: "
          f"{sum(1 for v in family_office.values() if v > 0)}, "
          f"max per family: {max(family_office.values()) if family_office else 0})")
    print(f"Output:   {output_path}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    generate(args.input, args.output)
