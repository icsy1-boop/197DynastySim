"use client";

import { SimEvent } from "@/lib/types";

interface Props {
  events: SimEvent[];
}

const TYPE_COLORS: Record<string, string> = {
  political:  "text-yellow-400",
  crime:      "text-red-400",
  corruption: "text-orange-400",
  civic:      "text-green-400",
  economy:    "text-blue-400",
};

const TYPE_BADGE: Record<string, string> = {
  political:  "bg-yellow-900 text-yellow-300",
  crime:      "bg-red-900 text-red-300",
  corruption: "bg-orange-900 text-orange-300",
  civic:      "bg-green-900 text-green-300",
  economy:    "bg-blue-900 text-blue-300",
};

export default function EventLog({ events }: Props) {
  const sorted = [...events].sort((a, b) => b.tick - a.tick).slice(0, 40);

  return (
    <div className="flex flex-col h-full">
      <div className="text-xs font-bold text-gray-400 px-3 py-2 border-b border-gray-700 uppercase tracking-wider">
        Events
      </div>
      <div className="flex-1 overflow-y-auto">
        {sorted.length === 0 ? (
          <div className="text-gray-500 text-xs p-3">No events this day.</div>
        ) : (
          sorted.map((ev, i) => (
            <div key={i} className="px-3 py-1.5 border-b border-gray-800 hover:bg-gray-800">
              <div className="flex gap-2 items-start">
                <span className={`text-xs px-1 rounded shrink-0 mt-0.5 ${TYPE_BADGE[ev.type] ?? "bg-gray-700 text-gray-300"}`}>
                  {ev.type}
                </span>
                <span className="text-xs text-gray-300 leading-tight">{ev.description}</span>
              </div>
              {ev.agent_name && ev.agent_name !== "SYSTEM" && (
                <div className="text-xs text-gray-500 mt-0.5 pl-1">— {ev.agent_name} (hr {ev.hour})</div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
