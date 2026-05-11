import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import { OUTPUT_DIR } from "@/lib/outputDir";

const DAY_FILE_RE = /^y\d{2}_d\d{3}\.json$/;

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ runId: string; dayFile: string }> }
) {
  const { runId, dayFile } = await params;

  // Validate path components to prevent traversal
  if (!DAY_FILE_RE.test(dayFile) || runId.includes("..") || runId.includes("/")) {
    return NextResponse.json({ error: "Invalid parameters" }, { status: 400 });
  }

  const filePath = path.join(OUTPUT_DIR, runId, "days", dayFile);
  if (!fs.existsSync(filePath)) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  const content = fs.readFileSync(filePath, "utf-8");
  return new NextResponse(content, {
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "public, max-age=86400, immutable",
    },
  });
}
