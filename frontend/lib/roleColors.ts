// Role → display color mapping for agent dots on the world map

export const ROLE_COLORS: Record<string, string> = {
  mayor:            "#f5c842",   // gold
  vice_mayor:       "#e8b800",   // dark gold
  councilor:        "#ffd700",   // light gold
  barangay_captain: "#ff9900",   // orange-gold
  contractor:       "#ff6600",   // orange
  journalist:       "#00ccff",   // cyan
  auditor:          "#00ff88",   // green
  police:           "#4488ff",   // blue
  teacher:          "#88ff44",   // light green
  nurse:            "#ff88cc",   // pink
  vendor:           "#cc8844",   // brown
  business_owner:   "#cc6600",   // dark orange
  farmer:           "#88aa44",   // olive
  informal_worker:  "#aaaaaa",   // grey
  student:          "#88ccff",   // light blue
  unemployed:       "#666666",   // dark grey
  elder:            "#ddbbaa",   // beige
};

export const POLITICAL_ROLES = new Set([
  "mayor", "vice_mayor", "councilor", "barangay_captain",
  "contractor", "journalist", "auditor", "police",
]);

export function getRoleColor(role: string): string {
  return ROLE_COLORS[role] ?? "#ffffff";
}

export function isPolitical(role: string): boolean {
  return POLITICAL_ROLES.has(role);
}

// Family ID → ring color (deterministic from string hash)
export function familyColor(familyId: string): string {
  let hash = 0;
  for (let i = 0; i < familyId.length; i++) {
    hash = (hash * 31 + familyId.charCodeAt(i)) >>> 0;
  }
  const hue = hash % 360;
  return `hsl(${hue}, 80%, 60%)`;
}
