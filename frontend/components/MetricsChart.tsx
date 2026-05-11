"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { TimeSeriesPoint } from "@/lib/types";
import { METRIC_LABELS, METRIC_COLORS } from "@/lib/replay";

interface Props {
  dynastyData: TimeSeriesPoint[];
  noDynastyData: TimeSeriesPoint[];
  metrics: string[];
  title?: string;
}

export default function MetricsChart({ dynastyData, noDynastyData, metrics, title }: Props) {
  // Merge by day index for side-by-side comparison
  const maxLen = Math.max(dynastyData.length, noDynastyData.length);
  const combined = Array.from({ length: maxLen }, (_, i) => {
    const d = dynastyData[i];
    const n = noDynastyData[i];
    const point: Record<string, number> = {
      day: d?.day ?? n?.day ?? i + 1,
      year: d?.year ?? n?.year ?? 1,
    };
    for (const m of metrics) {
      if (d) point[`dynasty_${m}`] = (d as unknown as Record<string, number>)[m];
      if (n) point[`nodyn_${m}`]   = (n as unknown as Record<string, number>)[m];
    }
    return point;
  });

  return (
    <div className="bg-gray-900 rounded-lg p-4 border border-gray-700">
      {title && <div className="text-sm font-bold text-gray-300 mb-3">{title}</div>}
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={combined} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis dataKey="day" tick={{ fill: "#9ca3af", fontSize: 10 }} />
          <YAxis domain={[0, 1]} tick={{ fill: "#9ca3af", fontSize: 10 }} />
          <Tooltip
            contentStyle={{ backgroundColor: "#1f2937", border: "1px solid #374151", borderRadius: 6 }}
            labelStyle={{ color: "#d1d5db" }}
            itemStyle={{ fontSize: 11 }}
          />
          <Legend wrapperStyle={{ fontSize: 10, color: "#9ca3af" }} />
          {metrics.map((m) => (
            <>
              <Line
                key={`dynasty_${m}`}
                type="monotone"
                dataKey={`dynasty_${m}`}
                stroke={METRIC_COLORS[m] ?? "#888"}
                strokeWidth={2}
                dot={false}
                name={`${METRIC_LABELS[m] ?? m} (dynasty)`}
              />
              <Line
                key={`nodyn_${m}`}
                type="monotone"
                dataKey={`nodyn_${m}`}
                stroke={METRIC_COLORS[m] ?? "#888"}
                strokeWidth={2}
                strokeDasharray="4 4"
                dot={false}
                name={`${METRIC_LABELS[m] ?? m} (no dynasty)`}
              />
            </>
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
