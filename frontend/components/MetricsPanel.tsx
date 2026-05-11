"use client";

import { GlobalState } from "@/lib/types";
import { METRIC_LABELS, METRIC_COLORS } from "@/lib/replay";

interface Props {
  global: GlobalState | null;
  dynastyEnabled?: boolean;
}

const DISPLAYED_METRICS = [
  "corruption_index",
  "welfare_index",
  "citizen_trust",
  "unrest_level",
  "dynasty_score",
  "audit_strength",
  "media_presence",
];

function MetricBar({ label, value, color }: { label: string; value: number; color: string }) {
  const pct = Math.round(value * 100);
  return (
    <div className="mb-2">
      <div className="flex justify-between text-xs mb-0.5">
        <span className="text-gray-400">{label}</span>
        <span style={{ color }}>{pct}%</span>
      </div>
      <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
    </div>
  );
}

export default function MetricsPanel({ global: g, dynastyEnabled }: Props) {
  if (!g) {
    return (
      <div className="p-3 text-gray-500 text-xs">No data loaded</div>
    );
  }

  return (
    <div className="p-3 space-y-1">
      <div className="text-xs font-bold text-gray-300 mb-2 uppercase tracking-wider">
        {dynastyEnabled !== undefined ? (dynastyEnabled ? "Dynasty" : "No Dynasty") : "Metrics"}
      </div>
      {DISPLAYED_METRICS.map((key) => (
        <MetricBar
          key={key}
          label={METRIC_LABELS[key] ?? key}
          value={(g as unknown as Record<string, number>)[key] ?? 0}
          color={METRIC_COLORS[key] ?? "#888"}
        />
      ))}
      <div className="mt-2 pt-2 border-t border-gray-700 text-xs">
        <span className="text-gray-400">Budget </span>
        <span className="text-white">₱{g.city_budget.toLocaleString()}</span>
      </div>
    </div>
  );
}
