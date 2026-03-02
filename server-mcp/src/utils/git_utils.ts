import * as fs from "fs";
import * as os from "os";
import * as path from "path";
import { runProcess } from "./process_utils.js";

export async function getGitDiff(repoPath: string): Promise<string> {
  const result = await runProcess("git", ["diff"], repoPath, 10_000);
  return result.stdout;
}

export async function applyGitPatch(
  repoPath: string,
  patchContent: string
): Promise<{ applied: boolean; error: string | null }> {
  const tmpFile = path.join(
    os.tmpdir(),
    `mcp_patch_${Date.now()}.patch`
  );
  try {
    fs.writeFileSync(tmpFile, patchContent, "utf8");
    const result = await runProcess(
      "git",
      ["apply", tmpFile],
      repoPath,
      10_000
    );
    if (result.exitCode === 0) {
      return { applied: true, error: null };
    }
    return {
      applied: false,
      error: result.stderr || result.stdout || "git apply failed",
    };
  } catch (err) {
    return {
      applied: false,
      error: err instanceof Error ? err.message : String(err),
    };
  } finally {
    try {
      fs.unlinkSync(tmpFile);
    } catch {
      // Temp file cleanup is best-effort
    }
  }
}
