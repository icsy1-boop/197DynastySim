"use client";

import { useState, useEffect } from "react";
import { Conversation, RunMetadata } from "@/lib/types";
import ConversationFeed from "@/components/ConversationFeed";
import { POLITICAL_ROLES } from "@/lib/roleColors";

export default function ConversationsPage() {
  const [runs, setRuns] = useState<RunMetadata[]>([]);
  const [runId, setRunId] = useState<string>("");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(false);
  const [filterYear, setFilterYear] = useState<string>("");
  const [filterDay, setFilterDay] = useState<string>("");
  const [searchText, setSearchText] = useState<string>("");

  useEffect(() => {
    fetch("/api/runs")
      .then((r) => r.json())
      .then(({ runs: r }) => setRuns(r ?? []))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!runId) return;
    setLoading(true);
    const params = new URLSearchParams({ runId, limit: "500" });
    if (filterYear) params.set("year", filterYear);
    if (filterDay)  params.set("day",  filterDay);
    fetch(`/api/conversations?${params}`)
      .then((r) => r.json())
      .then(({ conversations: c }) => setConversations(c ?? []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [runId, filterYear, filterDay]);

  const filtered = conversations.filter((c) => {
    if (searchText) {
      const q = searchText.toLowerCase();
      return (
        c.agent_a_name.toLowerCase().includes(q) ||
        c.agent_b_name.toLowerCase().includes(q) ||
        c.dialogue.toLowerCase().includes(q)
      );
    }
    return true;
  });

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Filter bar */}
      <div className="bg-gray-900 border-b border-gray-700 px-4 py-2 flex flex-wrap gap-3 items-center shrink-0">
        <select
          value={runId}
          onChange={(e) => setRunId(e.target.value)}
          className="bg-gray-800 text-white text-xs border border-gray-600 rounded px-2 py-1"
        >
          <option value="">— select run —</option>
          {runs.map((r) => (
            <option key={r.run_id} value={r.run_id}>{r.run_id}</option>
          ))}
        </select>
        <input
          type="number" min={1} max={6} placeholder="Year"
          value={filterYear}
          onChange={(e) => setFilterYear(e.target.value)}
          className="w-16 bg-gray-800 text-white text-xs border border-gray-600 rounded px-2 py-1"
        />
        <input
          type="number" min={1} max={365} placeholder="Day"
          value={filterDay}
          onChange={(e) => setFilterDay(e.target.value)}
          className="w-16 bg-gray-800 text-white text-xs border border-gray-600 rounded px-2 py-1"
        />
        <input
          type="text" placeholder="Search name or dialogue…"
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          className="flex-1 min-w-[140px] bg-gray-800 text-white text-xs border border-gray-600 rounded px-2 py-1"
        />
        <span className="text-xs text-gray-500">{filtered.length} conversations</span>
      </div>

      {/* Conversation list */}
      <div className="flex-1 overflow-y-auto p-4">
        {loading ? (
          <div className="text-gray-500 text-sm">Loading…</div>
        ) : (
          <ConversationFeed conversations={filtered} />
        )}
      </div>
    </div>
  );
}
