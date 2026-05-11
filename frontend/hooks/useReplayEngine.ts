"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { DaySnapshot, PlaybackSpeed, PlaybackState, ReplayState } from "@/lib/types";
import { dayFileName } from "@/lib/replay";
import { prefetchDay } from "./useDayData";

const DAY_CACHE = new Map<string, DaySnapshot>();

async function loadDay(runId: string, year: number, day: number): Promise<DaySnapshot | null> {
  const key = `${runId}/${dayFileName(year, day)}`;
  if (DAY_CACHE.has(key)) return DAY_CACHE.get(key)!;
  try {
    const r = await fetch(`/api/runs/${encodeURIComponent(runId)}/days/${dayFileName(year, day)}`);
    if (!r.ok) return null;
    const json: DaySnapshot = await r.json();
    DAY_CACHE.set(key, json);
    return json;
  } catch {
    return null;
  }
}

export function useReplayEngine(maxYear: number = 6) {
  const [state, setState] = useState<ReplayState>({
    runId: null,
    currentYear: 1,
    currentDay: 1,
    currentHour: 0,
    playback: "paused",
    speed: 1,
    dayData: null,
    loading: false,
    error: null,
  });

  const rafRef = useRef<number>(0);
  const lastTickRef = useRef<number>(0);
  const stateRef = useRef(state);
  stateRef.current = state;

  // Load day data when year/day/runId changes
  useEffect(() => {
    if (!state.runId) return;
    setState((s) => ({ ...s, loading: true, error: null }));
    loadDay(state.runId, state.currentYear, state.currentDay).then((data) => {
      setState((s) => ({ ...s, dayData: data, loading: false, error: data ? null : "Day not found" }));
    });
    // Prefetch next day
    prefetchDay(state.runId, state.currentYear, state.currentDay);
  }, [state.runId, state.currentYear, state.currentDay]);

  // requestAnimationFrame loop for hour advancement
  useEffect(() => {
    function tick(timestamp: number) {
      const s = stateRef.current;
      if (s.playback !== "playing") {
        rafRef.current = requestAnimationFrame(tick);
        return;
      }

      // Advance 1 sim-hour every (1000ms / speed)
      const msPerHour = 1000 / s.speed;
      if (timestamp - lastTickRef.current >= msPerHour) {
        lastTickRef.current = timestamp;

        setState((prev) => {
          const nextHour = prev.currentHour + 1;
          if (nextHour > 23) {
            // Advance to next day
            const nextDay = prev.currentDay < 365 ? prev.currentDay + 1 : 1;
            const nextYear = prev.currentDay < 365 ? prev.currentYear : prev.currentYear + 1;
            if (nextYear > maxYear) {
              return { ...prev, playback: "paused", currentHour: 23 };
            }
            return { ...prev, currentHour: 0, currentDay: nextDay, currentYear: nextYear };
          }
          return { ...prev, currentHour: nextHour };
        });
      }

      rafRef.current = requestAnimationFrame(tick);
    }

    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [maxYear]);

  const setRunId = useCallback((runId: string) => {
    setState((s) => ({
      ...s, runId, currentYear: 1, currentDay: 1, currentHour: 0,
      playback: "paused", dayData: null,
    }));
  }, []);

  const play  = useCallback(() => setState((s) => ({ ...s, playback: "playing" })), []);
  const pause = useCallback(() => setState((s) => ({ ...s, playback: "paused" })), []);
  const togglePlay = useCallback(() => setState((s) => ({
    ...s, playback: s.playback === "playing" ? "paused" : "playing",
  })), []);

  const setSpeed = useCallback((speed: PlaybackSpeed) => setState((s) => ({ ...s, speed })), []);

  const seekDay = useCallback((year: number, day: number) => {
    setState((s) => ({ ...s, currentYear: year, currentDay: day, currentHour: 0, playback: "paused" }));
  }, []);

  return { state, setRunId, play, pause, togglePlay, setSpeed, seekDay };
}
