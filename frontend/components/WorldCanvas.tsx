"use client";

import { useRef, useEffect, useCallback } from "react";
import { AgentSnapshot, Conversation, DaySnapshot } from "@/lib/types";
import { ZONE_LIST, getZone, zoneCenter } from "@/lib/locations";
import { getRoleColor, isPolitical, familyColor } from "@/lib/roleColors";
import { agentCanvasPos } from "@/lib/replay";

interface Props {
  dayData: DaySnapshot | null;
  prevDayData: DaySnapshot | null;
  currentHour: number;
  onAgentClick: (agent: AgentSnapshot) => void;
  highlightAgentId?: number | null;
  dynastyMode?: boolean;
}

export default function WorldCanvas({
  dayData,
  prevDayData,
  currentHour,
  onAgentClick,
  highlightAgentId,
  dynastyMode = false,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const hoveredRef = useRef<AgentSnapshot | null>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const W = canvas.width;
    const H = canvas.height;

    // Background
    ctx.fillStyle = "#1c3a1c";
    ctx.fillRect(0, 0, W, H);

    // Draw zones
    for (const zone of ZONE_LIST) {
      const x = zone.x * W;
      const y = zone.y * H;
      const w = zone.w * W;
      const h = zone.h * H;

      ctx.fillStyle = zone.fillColor + "cc"; // slight transparency
      ctx.strokeStyle = zone.strokeColor;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.roundRect(x, y, w, h, 4);
      ctx.fill();
      ctx.stroke();

      // Label
      ctx.fillStyle = "#ffffff99";
      ctx.font = `bold ${Math.max(8, Math.min(11, w / 6))}px monospace`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(zone.label, x + w / 2, y + h / 2);
    }

    if (!dayData) return;

    const agents = dayData.agents;
    const conversations = dayData.conversations.filter(
      (c) => c.hour === currentHour
    );

    // Draw agents
    for (const agent of agents) {
      const pos = agentCanvasPos(agent, currentHour, prevDayData, W, H);
      const color = getRoleColor(agent.role);
      const political = isPolitical(agent.role);
      const r = political ? 5 : 3;
      const isHighlighted = highlightAgentId === agent.id;

      // Family ring (dynasty mode)
      if (dynastyMode && agent.family_id) {
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, r + 3, 0, Math.PI * 2);
        ctx.strokeStyle = familyColor(agent.family_id);
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }

      // Highlight ring
      if (isHighlighted) {
        ctx.beginPath();
        ctx.arc(pos.x, pos.y, r + 5, 0, Math.PI * 2);
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      // Agent dot
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, r, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();

      // Name label for political agents
      if (political) {
        ctx.fillStyle = "#ffffffcc";
        ctx.font = "8px monospace";
        ctx.textAlign = "center";
        ctx.textBaseline = "top";
        const shortName = agent.name.split(" ")[0];
        ctx.fillText(shortName, pos.x, pos.y + r + 1);
      }

      // Conversation marker (speech bubble dot)
      const inConvo = conversations.some(
        (c) => c.agent_a_id === agent.id || c.agent_b_id === agent.id
      );
      if (inConvo) {
        ctx.beginPath();
        ctx.arc(pos.x + r, pos.y - r, 3, 0, Math.PI * 2);
        ctx.fillStyle = "#ffffff";
        ctx.fill();
      }
    }
  }, [dayData, prevDayData, currentHour, highlightAgentId, dynastyMode]);

  // Resize canvas to parent
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const obs = new ResizeObserver(() => {
      canvas.width  = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
      draw();
    });
    obs.observe(canvas.parentElement!);
    return () => obs.disconnect();
  }, [draw]);

  // Redraw on state changes
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || canvas.width === 0) return;
    draw();
  }, [draw]);

  // Agent hit-testing for click and hover
  const getAgentAt = useCallback(
    (clientX: number, clientY: number): AgentSnapshot | null => {
      const canvas = canvasRef.current;
      if (!canvas || !dayData) return null;
      const rect = canvas.getBoundingClientRect();
      const mx = clientX - rect.left;
      const my = clientY - rect.top;
      const W = canvas.width;
      const H = canvas.height;

      for (const agent of dayData.agents) {
        const pos = agentCanvasPos(agent, currentHour, prevDayData, W, H);
        const r = isPolitical(agent.role) ? 8 : 5;
        if (Math.hypot(pos.x - mx, pos.y - my) <= r) return agent;
      }
      return null;
    },
    [dayData, prevDayData, currentHour]
  );

  const handleClick = useCallback(
    (e: React.MouseEvent) => {
      const agent = getAgentAt(e.clientX, e.clientY);
      if (agent) onAgentClick(agent);
    },
    [getAgentAt, onAgentClick]
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      const agent = getAgentAt(e.clientX, e.clientY);
      hoveredRef.current = agent;
      const tooltip = tooltipRef.current;
      if (!tooltip) return;
      if (agent) {
        tooltip.style.display = "block";
        tooltip.style.left = `${e.clientX + 12}px`;
        tooltip.style.top  = `${e.clientY + 12}px`;
        tooltip.innerHTML = `
          <div class="font-bold">${agent.name}</div>
          <div class="text-xs opacity-70">${agent.role} · ${agent.location}</div>
          <div class="text-xs">sat=${agent.satisfaction} wealth=₱${agent.wealth.toLocaleString()}</div>
          <div class="text-xs">corrupt=${agent.corrupt_acts} honest=${agent.honest_acts}</div>
        `;
      } else {
        tooltip.style.display = "none";
      }
    },
    [getAgentAt]
  );

  return (
    <div className="relative w-full h-full">
      <canvas
        ref={canvasRef}
        className="w-full h-full cursor-pointer"
        onClick={handleClick}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => {
          if (tooltipRef.current) tooltipRef.current.style.display = "none";
        }}
      />
      <div
        ref={tooltipRef}
        className="fixed z-50 bg-gray-900 border border-gray-600 text-white text-xs p-2 rounded pointer-events-none"
        style={{ display: "none" }}
      />
    </div>
  );
}
