// Zone definitions mirroring sim/world/locations.py

export type ZoneType = "government" | "commercial" | "civic" | "residential" | "agricultural" | "industrial";

export interface ZoneDefinition {
  key: string;
  label: string;
  zone_type: ZoneType;
  x: number;
  y: number;
  w: number;
  h: number;
  fillColor: string;
  strokeColor: string;
}

export const ZONES: Record<string, ZoneDefinition> = {
  farm:       { key: "farm",       label: "FARM",           zone_type: "agricultural", x: 0.18, y: 0.32, w: 0.14, h: 0.16, fillColor: "#5a3a1a", strokeColor: "#3a2208" },
  factory:    { key: "factory",    label: "FACTORIES",      zone_type: "industrial",   x: 0.46, y: 0.10, w: 0.22, h: 0.16, fillColor: "#444",    strokeColor: "#333"    },
  church:     { key: "church",     label: "CHURCH",         zone_type: "civic",        x: 0.44, y: 0.38, w: 0.08, h: 0.07, fillColor: "#1a5c1a", strokeColor: "#0f3a0f" },
  school:     { key: "school",     label: "SCHOOL",         zone_type: "civic",        x: 0.38, y: 0.42, w: 0.09, h: 0.07, fillColor: "#1a5c1a", strokeColor: "#0f3a0f" },
  hospital:   { key: "hospital",   label: "HOSPITAL",       zone_type: "civic",        x: 0.56, y: 0.38, w: 0.11, h: 0.07, fillColor: "#1a5c1a", strokeColor: "#0f3a0f" },
  park:       { key: "park",       label: "PARK",           zone_type: "civic",        x: 0.40, y: 0.50, w: 0.08, h: 0.07, fillColor: "#1a5c1a", strokeColor: "#0f3a0f" },
  media:      { key: "media",      label: "MEDIA",          zone_type: "civic",        x: 0.54, y: 0.48, w: 0.08, h: 0.07, fillColor: "#1a5c1a", strokeColor: "#0f3a0f" },
  bgyhall:    { key: "bgyhall",    label: "BRGY HALL",      zone_type: "government",   x: 0.64, y: 0.48, w: 0.08, h: 0.07, fillColor: "#8b1a1a", strokeColor: "#6b0f0f" },
  market:     { key: "market",     label: "MARKET",         zone_type: "commercial",   x: 0.42, y: 0.58, w: 0.10, h: 0.07, fillColor: "#7a5230", strokeColor: "#5a3a1a" },
  police:     { key: "police",     label: "POLICE",         zone_type: "government",   x: 0.54, y: 0.57, w: 0.07, h: 0.06, fillColor: "#8b1a1a", strokeColor: "#6b0f0f" },
  audit:      { key: "audit",      label: "AUDIT",          zone_type: "government",   x: 0.63, y: 0.57, w: 0.06, h: 0.06, fillColor: "#8b1a1a", strokeColor: "#6b0f0f" },
  sarisari:   { key: "sarisari",   label: "SARI-SARI",      zone_type: "commercial",   x: 0.34, y: 0.62, w: 0.07, h: 0.07, fillColor: "#7a5230", strokeColor: "#5a3a1a" },
  contoffice: { key: "contoffice", label: "CONTRACTOR",     zone_type: "commercial",   x: 0.38, y: 0.68, w: 0.07, h: 0.06, fillColor: "#7a5230", strokeColor: "#5a3a1a" },
  bank:       { key: "bank",       label: "BANK",           zone_type: "commercial",   x: 0.46, y: 0.68, w: 0.07, h: 0.06, fillColor: "#7a5230", strokeColor: "#5a3a1a" },
  munhall:    { key: "munhall",    label: "MUNICIPAL HALL", zone_type: "government",   x: 0.54, y: 0.63, w: 0.12, h: 0.09, fillColor: "#8b1a1a", strokeColor: "#6b0f0f" },
  resA:       { key: "resA",       label: "RES. A",         zone_type: "residential",  x: 0.74, y: 0.55, w: 0.14, h: 0.18, fillColor: "#1e4d8c", strokeColor: "#1a3a6b" },
  resB:       { key: "resB",       label: "RES. B",         zone_type: "residential",  x: 0.42, y: 0.80, w: 0.20, h: 0.12, fillColor: "#7a2a8c", strokeColor: "#5a1a6b" },
  resC:       { key: "resC",       label: "RES. C",         zone_type: "residential",  x: 0.12, y: 0.55, w: 0.22, h: 0.22, fillColor: "#b36000", strokeColor: "#8b4a00" },
};

export const ZONE_LIST = Object.values(ZONES);

export function getZone(key: string): ZoneDefinition | undefined {
  return ZONES[key];
}

export function zoneCenter(zone: ZoneDefinition, canvasW: number, canvasH: number): { x: number; y: number } {
  return {
    x: (zone.x + zone.w / 2) * canvasW,
    y: (zone.y + zone.h / 2) * canvasH,
  };
}
