import { NextRequest, NextResponse } from "next/server";
import path from "path";
import fs from "fs";
import { OUTPUT_DIR } from "@/lib/outputDir";

export async function GET(req: NextRequest) {
  const { searchParams } = req.nextUrl;
  const runId    = searchParams.get("runId") ?? "";
  const year     = searchParams.get("year");
  const day      = searchParams.get("day");
  const agentId  = searchParams.get("agentId");
  const limit    = Math.min(parseInt(searchParams.get("limit") ?? "200"), 500);

  if (!runId || runId.includes("..") || runId.includes("/")) {
    return NextResponse.json({ error: "Invalid runId" }, { status: 400 });
  }

  const dbPath = path.join(OUTPUT_DIR, `${runId}.db`);
  if (!fs.existsSync(dbPath)) {
    return NextResponse.json({ conversations: [] });
  }

  try {
    const Database = (await import("better-sqlite3")).default;
    const db = new Database(dbPath, { readonly: true });

    const conditions: string[] = [];
    const bindings: (string | number)[] = [];

    if (year)    { conditions.push("year = ?");    bindings.push(parseInt(year)); }
    if (day)     { conditions.push("day = ?");     bindings.push(parseInt(day)); }
    if (agentId) {
      conditions.push("(agent_a_id = ? OR agent_b_id = ?)");
      bindings.push(parseInt(agentId), parseInt(agentId));
    }

    const where = conditions.length ? `WHERE ${conditions.join(" AND ")}` : "";
    const rows = db
      .prepare(`SELECT * FROM conversations ${where} ORDER BY tick DESC LIMIT ?`)
      .all(...bindings, limit) as unknown[];

    db.close();
    return NextResponse.json({ conversations: rows });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
