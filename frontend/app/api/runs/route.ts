import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import { OUTPUT_DIR } from "@/lib/outputDir";
import type { RunMetadata } from "@/lib/types";

export async function GET() {
  try {
    if (!fs.existsSync(OUTPUT_DIR)) {
      return NextResponse.json({ runs: [] });
    }

    const entries = fs.readdirSync(OUTPUT_DIR, { withFileTypes: true });
    const runs: RunMetadata[] = [];

    for (const entry of entries) {
      if (!entry.isDirectory()) continue;
      const runId = entry.name;
      const daysDir = path.join(OUTPUT_DIR, runId, "days");
      if (!fs.existsSync(daysDir)) continue;

      const dayFiles = fs
        .readdirSync(daysDir)
        .filter((f) => /^y\d{2}_d\d{3}\.json$/.test(f))
        .sort();

      runs.push({
        run_id: runId,
        dynasty_enabled: runId.includes("_dynasty_") && !runId.includes("no_dynasty"),
        total_days: dayFiles.length,
        day_files: dayFiles,
      });
    }

    return NextResponse.json({ runs });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
