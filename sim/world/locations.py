"""
world/locations.py
All named locations in Barangay Mabuhay.
Matches the map zones from the frontend.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Location:
    key: str
    label: str
    zone_type: str          # government | commercial | civic | residential | agricultural | industrial
    capacity: int           # max agents before it feels 'crowded'
    x: float                # normalized 0-1 (matches frontend)
    y: float
    w: float
    h: float
    current_agents: List[int] = field(default_factory=list)   # agent ids present

    def is_crowded(self) -> bool:
        return len(self.current_agents) > self.capacity

    def add_agent(self, agent_id: int):
        if agent_id not in self.current_agents:
            self.current_agents.append(agent_id)

    def remove_agent(self, agent_id: int):
        if agent_id in self.current_agents:
            self.current_agents.remove(agent_id)


LOCATIONS: dict[str, Location] = {
    "farm":       Location("farm",       "Farm",              "agricultural", 80,  .18, .32, .14, .16),
    "factory":    Location("factory",    "Factories",         "industrial",   120, .46, .10, .22, .16),
    "church":     Location("church",     "Church",            "civic",        60,  .44, .38, .08, .07),
    "school":     Location("school",     "School",            "civic",        200, .38, .42, .09, .07),
    "hospital":   Location("hospital",   "Hospital",          "civic",        80,  .56, .38, .11, .07),
    "park":       Location("park",       "Park",              "civic",        150, .40, .50, .08, .07),
    "media":      Location("media",      "Media Station",     "civic",        20,  .54, .48, .08, .07),
    "bgyhall":    Location("bgyhall",    "Barangay Hall",     "government",   40,  .64, .48, .08, .07),
    "market":     Location("market",     "Market",            "commercial",   300, .42, .58, .10, .07),
    "police":     Location("police",     "Police Station",    "government",   30,  .54, .57, .07, .06),
    "audit":      Location("audit",      "Audit Office",      "government",   15,  .63, .57, .06, .06),
    "sarisari":   Location("sarisari",   "Sari-Sari Stores",  "commercial",   50,  .34, .62, .07, .07),
    "contoffice": Location("contoffice", "Contractor Office", "commercial",   20,  .38, .68, .07, .06),
    "bank":       Location("bank",       "Bank",              "commercial",   40,  .46, .68, .07, .06),
    "munhall":    Location("munhall",    "Municipal Hall",    "government",   60,  .54, .63, .12, .09),
    "resA":       Location("resA",       "Residential A",     "residential",  600, .74, .55, .14, .18),
    "resB":       Location("resB",       "Residential B",     "residential",  1600,.42, .80, .20, .12),
    "resC":       Location("resC",       "Residential C",     "residential",  2800,.12, .55, .22, .22),
}


def get_location(key: str) -> Optional[Location]:
    return LOCATIONS.get(key)


def government_locations() -> List[str]:
    return [k for k, v in LOCATIONS.items() if v.zone_type == "government"]


def civic_locations() -> List[str]:
    return [k for k, v in LOCATIONS.items() if v.zone_type == "civic"]
