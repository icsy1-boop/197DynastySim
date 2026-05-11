"use client";

import { Conversation } from "@/lib/types";

interface Props {
  conversations: Conversation[];
}

const OUTCOME_BADGE: Record<string, string> = {
  positive: "bg-green-900 text-green-300",
  negative: "bg-red-900 text-red-300",
  neutral:  "bg-gray-700 text-gray-300",
};

export default function ConversationFeed({ conversations }: Props) {
  if (conversations.length === 0) {
    return (
      <div className="text-gray-500 text-sm p-4">No conversations recorded for this selection.</div>
    );
  }

  return (
    <div className="space-y-3">
      {conversations.map((conv, i) => (
        <div key={i} className="bg-gray-800 rounded-lg p-3 border border-gray-700">
          <div className="flex items-center justify-between mb-1">
            <div className="text-sm font-semibold text-yellow-300">
              {conv.agent_a_name}
              <span className="text-gray-500 mx-1">→</span>
              {conv.agent_b_name}
            </div>
            <div className="flex gap-2 items-center">
              <span className={`text-xs px-1.5 py-0.5 rounded ${OUTCOME_BADGE[conv.outcome] ?? OUTCOME_BADGE.neutral}`}>
                {conv.outcome}
              </span>
              <span className="text-xs text-gray-500">{conv.location} · hr {conv.hour}</span>
            </div>
          </div>
          <div className="text-gray-200 italic text-sm">
            &ldquo;{conv.dialogue}&rdquo;
          </div>
        </div>
      ))}
    </div>
  );
}
