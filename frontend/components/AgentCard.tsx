"use client";

import { AgentSnapshot } from "@/lib/types";
import { getRoleColor, isPolitical } from "@/lib/roleColors";
import MemoryStreamPanel from "./MemoryStreamPanel";

interface Props {
  agent: AgentSnapshot | null;
  onClose: () => void;
}

export default function AgentCard({ agent, onClose }: Props) {
  if (!agent) return null;

  const color = getRoleColor(agent.role);

  return (
    <div className="flex flex-col h-full bg-gray-900 border-l border-gray-700 overflow-y-auto">
      {/* Header */}
      <div className="flex items-start justify-between p-3 border-b border-gray-700">
        <div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
            <span className="font-bold text-white">{agent.name}</span>
          </div>
          <div className="text-xs text-gray-400 mt-0.5">
            {agent.role} · {agent.location}
            {agent.family_id && <span className="ml-2 text-yellow-500">({agent.family_id} family)</span>}
          </div>
        </div>
        <button onClick={onClose} className="text-gray-500 hover:text-white text-lg leading-none">×</button>
      </div>

      <div className="p-3 space-y-4 text-xs">
        {/* Stats */}
        <div className="grid grid-cols-2 gap-2">
          <StatBox label="Satisfaction" value={`${agent.satisfaction}/100`} />
          <StatBox label="Wealth" value={`₱${agent.wealth.toLocaleString()}`} />
          <StatBox label="Corrupt acts" value={String(agent.corrupt_acts)} red />
          <StatBox label="Honest acts" value={String(agent.honest_acts)} />
        </div>

        {/* Traits */}
        <div>
          <div className="text-gray-400 uppercase tracking-wider mb-1">Traits</div>
          {Object.entries(agent.traits).map(([k, v]) => (
            <div key={k} className="flex justify-between mb-0.5">
              <span className="text-gray-400 capitalize">{k.replace("_", " ")}</span>
              <span className="text-white">{(v as number).toFixed(2)}</span>
            </div>
          ))}
        </div>

        {/* Goals */}
        <div>
          <div className="text-gray-400 uppercase tracking-wider mb-1">Goals</div>
          {agent.goals.map((g) => (
            <div key={g.key} className="mb-1">
              <div className="flex justify-between">
                <span className={g.public ? "text-gray-300" : "text-red-400"}>{g.label}</span>
                <span className="text-gray-500">{Math.round(g.progress * 100)}%</span>
              </div>
              <div className="h-1 bg-gray-700 rounded mt-0.5">
                <div className="h-full bg-blue-600 rounded" style={{ width: `${g.progress * 100}%` }} />
              </div>
            </div>
          ))}
        </div>

        {/* Daily plan */}
        {agent.daily_plan && (
          <div>
            <div className="text-gray-400 uppercase tracking-wider mb-1">Today&apos;s Plan</div>
            <div className="text-gray-300 italic leading-snug">{agent.daily_plan}</div>
          </div>
        )}

        {/* Memory stream (political agents only) */}
        {agent.memory_stream && isPolitical(agent.role) && (
          <MemoryStreamPanel memories={agent.memory_stream} />
        )}
      </div>
    </div>
  );
}

function StatBox({
  label, value, red,
}: { label: string; value: string; red?: boolean }) {
  return (
    <div className="bg-gray-800 rounded p-2">
      <div className="text-gray-500 text-xs">{label}</div>
      <div className={`font-bold ${red ? "text-red-400" : "text-white"}`}>{value}</div>
    </div>
  );
}
