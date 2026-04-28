import * as fs from "fs";
import * as os from "os";
import * as path from "path";
import { runProcess } from "./process_utils.js";

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function stripRepoPrefix(text: string, repoPath: string): string {
  const repoName = path.basename(path.resolve(repoPath));
  const escaped = escapeRegExp(repoName);

  return text
    .replace(new RegExp(`(diff --git a/)${escaped}/`, "g"), "$1")
    .replace(new RegExp(`( b/)${escaped}/`, "g"), "$1")
    .replace(new RegExp(`(--- a/)${escaped}/`, "g"), "$1")
    .replace(new RegExp(`(\\+\\+\\+ b/)${escaped}/`, "g"), "$1")
    .replace(new RegExp(`(rename from )${escaped}/`, "g"), "$1")
    .replace(new RegExp(`(rename to )${escaped}/`, "g"), "$1");
}

function sanitizePatchContent(patchContent: string, repoPath: string): string {
  let text = patchContent.trim();

  const fenced = text.match(/```(?:diff|patch)?\s*([\s\S]*?)```/i);
  if (fenced?.[1]) {
    text = fenced[1].trim();
  }

  const lines = text.split(/\r?\n/);
  const firstPatchLine = lines.findIndex(
    (line) =>
      line.startsWith("diff --git ") ||
      line.startsWith("--- ") ||
      line.startsWith("*** Begin Patch"),
  );

  if (firstPatchLine > 0) {
    text = lines.slice(firstPatchLine).join("\n");
  }

  return stripRepoPrefix(text, repoPath);
}

export async function getGitDiff(repoPath: string): Promise<string> {
  const result = await runProcess("git", ["diff"], repoPath, 10_000);
  return stripRepoPrefix(result.stdout, repoPath);
}

export async function applyGitPatch(
  repoPath: string,
  patchContent: string
): Promise<{ applied: boolean; error: string | null }> {
  const normalizedPatch = sanitizePatchContent(patchContent, repoPath);
  const tmpFile = path.join(
    os.tmpdir(),
    `mcp_patch_${Date.now()}.patch`
  );
  try {
    fs.writeFileSync(tmpFile, normalizedPatch, "utf8");
    const result = await runProcess(
      "git",
      ["apply", tmpFile],
      repoPath,
      10_000
    );
    if (result.exitCode === 0) {
      return { applied: true, error: null };
    }
    const rawError = result.stderr || result.stdout || "git apply failed";
    const error =
      rawError.includes("No valid patches in input")
        ? `${rawError.trim()}\napply_patch expects a raw unified diff patch with lines like:\n--- a/pyservicelab/auth/tokens.py\n+++ b/pyservicelab/auth/tokens.py\n@@ ...\nDo not send prose or only replacement code.`
        : rawError;
    return {
      applied: false,
      error,
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
