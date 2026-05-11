"use client";

import { PlaybackSpeed, RunMetadata } from "@/lib/types";
import { formatSimTime } from "@/lib/replay";

interface Props {
  runs: RunMetadata[];
  runId: string | null;
  onRunChange: (id: string) => void;
  year: number;
  day: number;
  hour: number;
  maxYear?: number;
  maxDay?: number;
  playback: "playing" | "paused";
  speed: PlaybackSpeed;
  onTogglePlay: () => void;
  onSpeedChange: (s: PlaybackSpeed) => void;
  onSeek: (year: number, day: number) => void;
  loading: boolean;
}

const SPEEDS: PlaybackSpeed[] = [1, 2, 5, 10];

export default function ReplayControls({
  runs, runId, onRunChange,
  year, day, hour,
  maxYear = 6, maxDay = 365,
  playback, speed,
  onTogglePlay, onSpeedChange, onSeek,
  loading,
}: Props) {
  const currentTotal = (year - 1) * 365 + day;
  const maxTotal     = maxYear * maxDay;

  return (
    <div className="flex items-center gap-3 bg-gray-900 border-b border-gray-700 px-4 py-2 flex-wrap">
      {/* Run selector */}
      <select
        value={runId ?? ""}
        onChange={(e) => onRunChange(e.target.value)}
        className="bg-gray-800 text-white text-xs border border-gray-600 rounded px-2 py-1"
      >
        <option value="">— select run —</option>
        {runs.map((r) => (
          <option key={r.run_id} value={r.run_id}>
            {r.run_id} ({r.dynasty_enabled ? "Dynasty" : "No Dynasty"})
          </option>
        ))}
      </select>

      {/* Play / Pause */}
      <button
        onClick={onTogglePlay}
        disabled={!runId || loading}
        className="bg-yellow-600 hover:bg-yellow-500 disabled:opacity-40 text-white text-xs px-3 py-1 rounded"
      >
        {loading ? "..." : playback === "playing" ? "⏸" : "▶"}
      </button>

      {/* Speed */}
      <div className="flex gap-1">
        {SPEEDS.map((s) => (
          <button
            key={s}
            onClick={() => onSpeedChange(s)}
            className={`text-xs px-2 py-1 rounded ${speed === s ? "bg-yellow-600 text-white" : "bg-gray-700 text-gray-300"}`}
          >
            {s}x
          </button>
        ))}
      </div>

      {/* Sim time display */}
      <span className="text-yellow-400 font-mono text-xs">
        {formatSimTime(year, day, hour)}
      </span>

      {/* Day scrubber */}
      {runId && (
        <input
          type="range"
          min={1}
          max={maxTotal}
          value={currentTotal}
          onChange={(e) => {
            const total = parseInt(e.target.value);
            const y = Math.floor((total - 1) / 365) + 1;
            const d = ((total - 1) % 365) + 1;
            onSeek(y, d);
          }}
          className="flex-1 min-w-[100px] accent-yellow-500"
        />
      )}
    </div>
  );
}
