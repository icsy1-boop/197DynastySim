import { NextRequest, NextResponse } from "next/server";
import path from "path";
import fs from "fs";
import { OUTPUT_DIR } from "@/lib/outputDir";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ runId: string }> }
) {
  const { runId } = await params;

  if (runId.includes("..") || runId.includes("/")) {
    return NextResponse.json({ error: "Invalid runId" }, { status: 400 });
  }

  const dbPath = path.join(OUTPUT_DIR, `${runId}.db`);
  if (!fs.existsSync(dbPath)) {
    return NextResponse.json({ history: [] });
  }

  try {
    // Dynamic import to avoid bundling issues
    const Database = (await import("better-sqlite3")).default;
    const db = new Database(dbPath, { readonly: true });
    const rows = db
      .prepare("SELECT * FROM global_state ORDER BY tick")
      .all() as unknown[];
    db.close();
    return NextResponse.json({ history: rows });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
