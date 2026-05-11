import path from "path";

// Resolve the simulation output directory.
// Override with DYNASTYSIM_OUTPUT_DIR env var for deployment.
export const OUTPUT_DIR =
  process.env.DYNASTYSIM_OUTPUT_DIR ??
  path.resolve(process.cwd(), "..", "output");
