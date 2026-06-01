"""
antidynasty_gen.py — derive anti-dynasty CSV from a base CSV.

Enforces: no family_id can have more than 1 member holding an OFFICIAL_ROLE.
Extras are demoted to civil_servant_admin (still Tier-1, but not "in office").

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

DEMOTION_ROLE = 'civil_servant_admin'


def generate(input_path, output_path):
    with open(input_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    family_official_seen = collections.defaultdict(int)
    demoted = 0

    for row in rows:
        if row['role'] in OFFICIAL_ROLES:
            fam = row['family_id']
            if family_official_seen[fam] >= 1:
                row['role'] = DEMOTION_ROLE
                demoted += 1
            else:
                family_official_seen[fam] += 1

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    officials_after = sum(1 for r in rows if r['role'] in OFFICIAL_ROLES)
    print(f"Input:   {len(rows)} agents")
    print(f"Demoted: {demoted} agents → {DEMOTION_ROLE}")
    print(f"Officials remaining: {officials_after}")
    print(f"Output:  {output_path}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    generate(args.input, args.output)
