"use client";

import { Conversation, DaySnapshot } from "@/lib/types";
import { agentCanvasPos } from "@/lib/replay";
import { isPolitical } from "@/lib/roleColors";

interface Props {
  conversations: Conversation[];
  dayData: DaySnapshot;
  prevDayData: DaySnapshot | null;
  currentHour: number;
  canvasRect: DOMRect | null;
  canvasW: number;
  canvasH: number;
}

export default function SpeechBubble({
  conversations,
  dayData,
  prevDayData,
  currentHour,
  canvasRect,
  canvasW,
  canvasH,
}: Props) {
  if (!canvasRect || conversations.length === 0) return null;

  // Show top 3 by importance (political agents first)
  const agentMap = new Map(dayData.agents.map((a) => [a.id, a]));
  const sorted = [...conversations].sort((a, b) => {
    const aaPol = isPolitical(agentMap.get(a.agent_a_id)?.role ?? "");
    const bbPol = isPolitical(agentMap.get(b.agent_a_id)?.role ?? "");
    return Number(bbPol) - Number(aaPol);
  });
  const visible = sorted.slice(0, 3);

  return (
    <>
      {visible.map((conv, i) => {
        const speaker = agentMap.get(conv.agent_a_id);
        if (!speaker) return null;

        const pos = agentCanvasPos(speaker, currentHour, prevDayData, canvasW, canvasH);
        // Scale canvas coords to screen coords
        const scaleX = canvasRect.width / canvasW;
        const scaleY = canvasRect.height / canvasH;
        const screenX = canvasRect.left + pos.x * scaleX;
        const screenY = canvasRect.top  + pos.y * scaleY;

        const outcomeColor = {
          positive: "border-green-500",
          negative: "border-red-500",
          neutral:  "border-gray-500",
        }[conv.outcome];

        return (
          <div
            key={`${conv.agent_a_id}-${conv.agent_b_id}-${i}`}
            className={`fixed z-40 max-w-[200px] bg-gray-900 border ${outcomeColor} rounded p-2 text-xs text-white pointer-events-none`}
            style={{
              left: screenX + 8,
              top: screenY - 60 - i * 70,
              transform: "translateX(-50%)",
            }}
          >
            <div className="font-bold text-yellow-300 truncate">
              {conv.agent_a_name} → {conv.agent_b_name}
            </div>
            <div className="mt-1 italic opacity-90 leading-tight">
              &ldquo;{conv.dialogue}&rdquo;
            </div>
          </div>
        );
      })}
    </>
  );
}
