"use client";

import { MemoryObject } from "@/lib/types";

interface Props {
  memories: MemoryObject[];
}

const TYPE_STYLE: Record<string, string> = {
  observation: "border-blue-600 bg-blue-950",
  reflection:  "border-purple-600 bg-purple-950",
  plan:        "border-yellow-600 bg-yellow-950",
};

const EMOTION_BADGE: Record<string, string> = {
  satisfied:  "text-green-400",
  frustrated: "text-orange-400",
  fearful:    "text-yellow-400",
  angry:      "text-red-400",
  neutral:    "text-gray-400",
};

function importanceBar(score: number) {
  const pct = (score / 10) * 100;
  const color = score >= 7 ? "#ef4444" : score >= 4 ? "#f97316" : "#6b7280";
  return (
    <div className="h-1 bg-gray-700 rounded-full mt-1">
      <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: color }} />
    </div>
  );
}

export default function MemoryStreamPanel({ memories }: Props) {
  const sorted = [...memories].sort((a, b) => b.importance - a.importance);

  return (
    <div>
      <div className="text-xs font-bold text-gray-400 mb-2 uppercase tracking-wider">
        Memory Stream ({memories.length})
      </div>
      <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
        {sorted.map((m) => (
          <div
            key={m.memory_id}
            className={`border-l-2 pl-2 py-1 text-xs rounded ${TYPE_STYLE[m.memory_type] ?? "border-gray-600 bg-gray-900"}`}
          >
            <div className="flex justify-between mb-0.5">
              <span className="text-gray-400 capitalize">{m.memory_type}</span>
              <span className={EMOTION_BADGE[m.emotional_tag] ?? "text-gray-400"}>
                {m.emotional_tag}
              </span>
            </div>
            <div className="text-gray-200 leading-tight">{m.description}</div>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-gray-500">imp: {m.importance.toFixed(1)}</span>
              <div className="flex-1">{importanceBar(m.importance)}</div>
            </div>
          </div>
        ))}
        {sorted.length === 0 && (
          <div className="text-gray-500">No memories yet.</div>
        )}
      </div>
    </div>
  );
}
