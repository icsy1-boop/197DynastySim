"use client";

import { useState, useEffect, useRef } from "react";
import { AgentSnapshot, RunMetadata, Conversation, DaySnapshot } from "@/lib/types";
import { useReplayEngine } from "@/hooks/useReplayEngine";
import WorldCanvas from "@/components/WorldCanvas";
import SpeechBubble from "@/components/SpeechBubble";
import ReplayControls from "@/components/ReplayControls";
import MetricsPanel from "@/components/MetricsPanel";
import EventLog from "@/components/EventLog";
import AgentCard from "@/components/AgentCard";

export default function ReplayPage() {
  const { state, setRunId, togglePlay, setSpeed, seekDay } = useReplayEngine();
  const [runs, setRuns] = useState<RunMetadata[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<AgentSnapshot | null>(null);
  const [prevDayData, setPrevDayData] = useState<DaySnapshot | null>(null);
  const [canvasRect, setCanvasRect] = useState<DOMRect | null>(null);
  const [canvasSize, setCanvasSize] = useState({ w: 800, h: 600 });
  const canvasWrapRef = useRef<HTMLDivElement>(null);

  // Load available runs
  useEffect(() => {
    fetch("/api/runs")
      .then((r) => r.json())
      .then(({ runs: r }) => setRuns(r ?? []))
      .catch(() => {});
  }, []);

  // Track canvas size/position for speech bubble overlay
  useEffect(() => {
    const el = canvasWrapRef.current;
    if (!el) return;
    const update = () => {
      setCanvasRect(el.getBoundingClientRect());
      setCanvasSize({ w: el.offsetWidth, h: el.offsetHeight });
    };
    const obs = new ResizeObserver(update);
    obs.observe(el);
    update();
    return () => obs.disconnect();
  }, []);

  // Keep prevDayData updated when day changes
  useEffect(() => {
    setPrevDayData(state.dayData);
  }, [state.currentDay, state.currentYear]);

  const currentConversations: Conversation[] =
    (state.dayData?.conversations ?? []).filter((c) => c.hour === state.currentHour);

  const dynastyEnabled =
    runs.find((r) => r.run_id === state.runId)?.dynasty_enabled ?? false;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Top controls */}
      <ReplayControls
        runs={runs}
        runId={state.runId}
        onRunChange={setRunId}
        year={state.currentYear}
        day={state.currentDay}
        hour={state.currentHour}
        maxDay={runs.find((r) => r.run_id === state.runId)?.total_days ?? 365}
        playback={state.playback}
        speed={state.speed}
        onTogglePlay={togglePlay}
        onSpeedChange={setSpeed}
        onSeek={seekDay}
        loading={state.loading}
      />

      {/* Main area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left sidebar — Metrics */}
        <div className="w-44 shrink-0 border-r border-gray-700 overflow-y-auto">
          <MetricsPanel global={state.dayData?.global ?? null} dynastyEnabled={dynastyEnabled} />
        </div>

        {/* Center — World canvas */}
        <div className="flex-1 flex flex-col overflow-hidden">
          <div ref={canvasWrapRef} className="flex-1 relative">
            <WorldCanvas
              dayData={state.dayData}
              prevDayData={prevDayData}
              currentHour={state.currentHour}
              onAgentClick={setSelectedAgent}
              highlightAgentId={selectedAgent?.id}
              dynastyMode={dynastyEnabled}
            />
            {/* Speech bubbles overlaid */}
            {state.dayData && (
              <SpeechBubble
                conversations={currentConversations}
                dayData={state.dayData}
                prevDayData={prevDayData}
                currentHour={state.currentHour}
                canvasRect={canvasRect}
                canvasW={canvasSize.w}
                canvasH={canvasSize.h}
              />
            )}
          </div>

          {/* Bottom event log */}
          <div className="h-36 border-t border-gray-700 overflow-hidden">
            <EventLog events={state.dayData?.events ?? []} />
          </div>
        </div>

        {/* Right panel — Agent detail */}
        <div className={`w-64 shrink-0 transition-all ${selectedAgent ? "" : "hidden"}`}>
          <AgentCard agent={selectedAgent} onClose={() => setSelectedAgent(null)} />
        </div>
      </div>
    </div>
  );
}
