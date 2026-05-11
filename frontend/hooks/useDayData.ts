"use client";

import { useState, useEffect, useRef } from "react";
import { DaySnapshot } from "@/lib/types";
import { dayFileName } from "@/lib/replay";

const cache = new Map<string, DaySnapshot>();

export function useDayData(runId: string | null, year: number, day: number) {
  const [data, setData] = useState<DaySnapshot | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) return;

    const key = `${runId}/${dayFileName(year, day)}`;

    if (cache.has(key)) {
      setData(cache.get(key)!);
      return;
    }

    setLoading(true);
    setError(null);

    fetch(`/api/runs/${encodeURIComponent(runId)}/days/${dayFileName(year, day)}`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((json: DaySnapshot) => {
        cache.set(key, json);
        setData(json);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [runId, year, day]);

  return { data, loading, error };
}

// Prefetch the next day in the background
export function prefetchDay(runId: string, year: number, day: number) {
  const nextDay = day < 365 ? day + 1 : 1;
  const nextYear = day < 365 ? year : year + 1;
  const key = `${runId}/${dayFileName(nextYear, nextDay)}`;
  if (cache.has(key)) return;

  fetch(`/api/runs/${encodeURIComponent(runId)}/days/${dayFileName(nextYear, nextDay)}`)
    .then((r) => r.ok ? r.json() : null)
    .then((json) => { if (json) cache.set(key, json); })
    .catch(() => {});
}
