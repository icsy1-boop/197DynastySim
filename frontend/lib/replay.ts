// Replay utilities: agent position interpolation, day file naming, tick math

import { AgentSnapshot, DaySnapshot } from "./types";
import { getZone, zoneCenter } from "./locations";

// Seeded LCG for deterministic per-agent jitter within zone bounds
function lcg(seed: number): () => number {
  let s = seed >>> 0;
  return () => {
    s = (Math.imul(1664525, s) + 1013904223) >>> 0;
    return s / 0xffffffff;
  };
}

export function agentCanvasPos(
  agent: AgentSnapshot,
  currentHour: number,
  prevDayData: DaySnapshot | null,
  canvasW: number,
  canvasH: number
): { x: number; y: number } {
  const zone = getZone(agent.location);
  if (!zone) return { x: canvasW / 2, y: canvasH / 2 };

  const rand = lcg(agent.id);
  const jitterX = (rand() - 0.5) * zone.w * canvasW * 0.7;
  const jitterY = (rand() - 0.5) * zone.h * canvasH * 0.7;

  const center = zoneCenter(zone, canvasW, canvasH);

  // Interpolate from previous day's location to today's using hour as t
  if (prevDayData && currentHour < 12) {
    const prevAgent = prevDayData.agents.find((a) => a.id === agent.id);
    if (prevAgent && prevAgent.location !== agent.location) {
      const prevZone = getZone(prevAgent.location);
      if (prevZone) {
        const prevCenter = zoneCenter(prevZone, canvasW, canvasH);
        const rand2 = lcg(agent.id + 9999);
        const pjx = (rand2() - 0.5) * prevZone.w * canvasW * 0.7;
        const pjy = (rand2() - 0.5) * prevZone.h * canvasH * 0.7;
        const t = currentHour / 23;
        return {
          x: (prevCenter.x + pjx) * (1 - t) + (center.x + jitterX) * t,
          y: (prevCenter.y + pjy) * (1 - t) + (center.y + jitterY) * t,
        };
      }
    }
  }

  return { x: center.x + jitterX, y: center.y + jitterY };
}

export function dayFileName(year: number, day: number): string {
  return `y${String(year).padStart(2, "0")}_d${String(day).padStart(3, "0")}.json`;
}

export function totalDays(year: number, day: number): number {
  return (year - 1) * 365 + day;
}

export function formatSimTime(year: number, day: number, hour: number): string {
  const hourStr = String(hour).padStart(2, "0");
  return `Year ${year} · Day ${day} · ${hourStr}:00`;
}

// Metric display labels
export const METRIC_LABELS: Record<string, string> = {
  corruption_index:     "Corruption",
  welfare_index:        "Welfare",
  citizen_trust:        "Trust",
  unrest_level:         "Unrest",
  dynasty_score:        "Dynasty",
  audit_strength:       "Audit",
  media_presence:       "Media",
  institution_strength: "Institutions",
};

export const METRIC_COLORS: Record<string, string> = {
  corruption_index:     "#ef4444",
  welfare_index:        "#22c55e",
  citizen_trust:        "#3b82f6",
  unrest_level:         "#f97316",
  dynasty_score:        "#a855f7",
  audit_strength:       "#06b6d4",
  media_presence:       "#eab308",
  institution_strength: "#64748b",
};
