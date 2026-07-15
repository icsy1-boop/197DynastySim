"""
barangay_roles.py — single source of truth for role sets.

Previously OFFICIAL_ROLES / POLITICAL_ROLES / WATCHDOG_ROLES were defined
independently in four modules and had drifted (barangay_mechanics counted
`contractor` as a political seat, which made the anti-dynasty arm log a
nonzero dynasty_bonus; barangay_unrest omitted treasurer/secretary). Every
live module imports from here now.
"""

# All seated officials: elected + appointed + municipal officers. Used for
# decision ticks, dynasty seat-share, protest exemption, election demotions.
OFFICIAL_ROLES = {
    "mayor", "vice_mayor", "councilor",
    "barangay_captain", "barangay_kagawad", "barangay_treasurer",
    "barangay_secretary", "municipal_engineer", "municipal_budget_officer",
    "municipal_treasurer", "procurement_officer", "business_permit_officer",
    "disaster_officer", "social_welfare_officer",
}

# Directly-voted seats only (RA 9164 / LGC).
ELECTED_ROLES = {
    "mayor", "vice_mayor", "councilor", "barangay_captain", "barangay_kagawad",
}

WATCHDOG_ROLES = {"local_journalist", "coa_auditor", "cso_organizer"}
