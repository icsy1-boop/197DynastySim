"use client";

import { useState, useEffect } from "react";
import { RunMetadata, TimeSeriesPoint } from "@/lib/types";
import MetricsChart from "@/components/MetricsChart";

const COMPARE_METRICS = [
  ["corruption_index"],
  ["welfare_index"],
  ["citizen_trust"],
  ["unrest_level"],
];

const TITLES = [
  "Corruption Index",
  "Welfare Index",
  "Citizen Trust",
  "Unrest Level",
];

async function fetchHistory(runId: string): Promise<TimeSeriesPoint[]> {
  try {
    const r = await fetch(`/api/runs/${encodeURIComponent(runId)}/global-history`);
    if (!r.ok) return [];
    const { history } = await r.json();
    // Sample to max 365 points per run (one per day)
    const raw: TimeSeriesPoint[] = history ?? [];
    const sampled: TimeSeriesPoint[] = [];
    for (let i = 0; i < raw.length; i++) {
      if (raw[i].hour === 0) sampled.push(raw[i]);
    }
    return sampled;
  } catch {
    return [];
  }
}

export default function ComparePage() {
  const [runs, setRuns] = useState<RunMetadata[]>([]);
  const [dynastyRunId, setDynastyRunId] = useState<string>("");
  const [noDynastyRunId, setNoDynastyRunId] = useState<string>("");
  const [dynastyHistory, setDynastyHistory] = useState<TimeSeriesPoint[]>([]);
  const [noDynastyHistory, setNoDynastyHistory] = useState<TimeSeriesPoint[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch("/api/runs")
      .then((r) => r.json())
      .then(({ runs: r }) => {
        setRuns(r ?? []);
        // Auto-select first dynasty and no-dynasty run
        const dyn = r?.find((x: RunMetadata) => x.dynasty_enabled);
        const nod = r?.find((x: RunMetadata) => !x.dynasty_enabled);
        if (dyn) setDynastyRunId(dyn.run_id);
        if (nod) setNoDynastyRunId(nod.run_id);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!dynastyRunId && !noDynastyRunId) return;
    setLoading(true);
    Promise.all([
      dynastyRunId ? fetchHistory(dynastyRunId) : Promise.resolve([]),
      noDynastyRunId ? fetchHistory(noDynastyRunId) : Promise.resolve([]),
    ]).then(([d, n]) => {
      setDynastyHistory(d);
      setNoDynastyHistory(n);
    }).finally(() => setLoading(false));
  }, [dynastyRunId, noDynastyRunId]);

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Run selector */}
      <div className="bg-gray-900 border-b border-gray-700 px-4 py-2 flex gap-4 items-center shrink-0">
        <label className="text-xs text-gray-400">
          Dynasty run:
          <select
            value={dynastyRunId}
            onChange={(e) => setDynastyRunId(e.target.value)}
            className="ml-2 bg-gray-800 text-white text-xs border border-gray-600 rounded px-2 py-1"
          >
            <option value="">—</option>
            {runs.map((r) => <option key={r.run_id} value={r.run_id}>{r.run_id}</option>)}
          </select>
        </label>
        <label className="text-xs text-gray-400">
          No-dynasty run:
          <select
            value={noDynastyRunId}
            onChange={(e) => setNoDynastyRunId(e.target.value)}
            className="ml-2 bg-gray-800 text-white text-xs border border-gray-600 rounded px-2 py-1"
          >
            <option value="">—</option>
            {runs.map((r) => <option key={r.run_id} value={r.run_id}>{r.run_id}</option>)}
          </select>
        </label>
        <span className="text-xs text-gray-500">solid = dynasty · dashed = no dynasty</span>
      </div>

      {/* Charts */}
      <div className="flex-1 overflow-y-auto p-4 grid grid-cols-1 md:grid-cols-2 gap-4">
        {loading ? (
          <div className="col-span-2 text-gray-500">Loading history data…</div>
        ) : dynastyHistory.length === 0 && noDynastyHistory.length === 0 ? (
          <div className="col-span-2 text-gray-500 text-sm">
            Select runs above to compare. Runs must be complete (have SQLite databases in the output/ directory).
          </div>
        ) : (
          COMPARE_METRICS.map((metrics, i) => (
            <MetricsChart
              key={metrics[0]}
              dynastyData={dynastyHistory}
              noDynastyData={noDynastyHistory}
              metrics={metrics}
              title={TITLES[i]}
            />
          ))
        )}
      </div>
    </div>
  );
}
