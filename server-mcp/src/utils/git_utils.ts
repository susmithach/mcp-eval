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

function normalizePathForFallback(filePath: string): string {
  return filePath
    .replace(/^a\//, "")
    .replace(/^b\//, "")
    .replace(/^target-repo\//, "");
}

function applyHunksToContent(content: string, hunkLines: string[]): string {
  const originalLines = content.split("\n");
  let currentLines = originalLines;
  let i = 0;

  while (i < hunkLines.length) {
    while (i < hunkLines.length && !hunkLines[i].startsWith("@@")) i++;
    if (i >= hunkLines.length) break;
    i++;

    const oldLines: string[] = [];
    const newLines: string[] = [];

    while (
      i < hunkLines.length &&
      !hunkLines[i].startsWith("@@") &&
      !hunkLines[i].startsWith("*** End Patch") &&
      !hunkLines[i].startsWith("*** Update File:") &&
      !hunkLines[i].startsWith("--- ") &&
      !hunkLines[i].startsWith("+++ ")
    ) {
      const line = hunkLines[i];
      if (line.startsWith(" ")) {
        oldLines.push(line.slice(1));
        newLines.push(line.slice(1));
      } else if (line.startsWith("-")) {
        oldLines.push(line.slice(1));
      } else if (line.startsWith("+")) {
        newLines.push(line.slice(1));
      }
      i++;
    }

    if (oldLines.length === 0 && newLines.length === 0) continue;

    const search = oldLines.join("\n");
    const replacement = newLines.join("\n");
    const current = currentLines.join("\n");
    const index = current.indexOf(search);
    if (index === -1) {
      throw new Error("Fallback patch apply failed: target hunk not found");
    }
    const updated = current.slice(0, index) + replacement + current.slice(index + search.length);
    currentLines = updated.split("\n");
  }

  return currentLines.join("\n");
}

function applyStructuredPatchFormat(repoPath: string, patchContent: string): boolean {
  const lines = patchContent.split(/\r?\n/);
  if (!lines[0]?.startsWith("*** Begin Patch")) return false;

  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (line.startsWith("*** Update File: ")) {
      const relativePath = normalizePathForFallback(
        line.slice("*** Update File: ".length).trim(),
      );
      i++;
      const hunkLines: string[] = [];
      while (i < lines.length && !lines[i].startsWith("*** Update File: ") && !lines[i].startsWith("*** End Patch")) {
        hunkLines.push(lines[i]);
        i++;
      }
      const absPath = path.join(repoPath, relativePath);
      const original = fs.readFileSync(absPath, "utf8");
      const updated = applyHunksToContent(original, hunkLines);
      fs.writeFileSync(absPath, updated, "utf8");
      continue;
    }
    i++;
  }

  return true;
}

function applyLooseUnifiedDiff(repoPath: string, patchContent: string): boolean {
  const lines = patchContent.split(/\r?\n/);
  const fromIndex = lines.findIndex((line) => line.startsWith("--- "));
  const toIndex = lines.findIndex((line) => line.startsWith("+++ "));
  const firstHunkIndex = lines.findIndex((line) => line.startsWith("@@"));
  if (fromIndex === -1 || firstHunkIndex === -1) {
    return false;
  }

  const headerLine =
    toIndex !== -1 ? lines[toIndex].slice("+++ ".length).trim() : lines[fromIndex].slice("--- ".length).trim();
  const relativePath = normalizePathForFallback(headerLine);
  const absPath = path.join(repoPath, relativePath);
  const original = fs.readFileSync(absPath, "utf8");
  const updated = applyHunksToContent(original, lines.slice(firstHunkIndex));
  fs.writeFileSync(absPath, updated, "utf8");
  return true;
}

function applyFallbackPatch(
  repoPath: string,
  patchContent: string,
): { applied: boolean; error: string | null } {
  try {
    if (applyStructuredPatchFormat(repoPath, patchContent)) {
      return { applied: true, error: null };
    }
    if (applyLooseUnifiedDiff(repoPath, patchContent)) {
      return { applied: true, error: null };
    }
    return {
      applied: false,
      error: "Fallback patch apply could not recognize the patch format.",
    };
  } catch (err) {
    return {
      applied: false,
      error: err instanceof Error ? err.message : String(err),
    };
  }
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
    const fallback = applyFallbackPatch(repoPath, normalizedPatch);
    if (fallback.applied) {
      return fallback;
    }
    const rawError = result.stderr || result.stdout || "git apply failed";
    const error =
      rawError.includes("No valid patches in input")
        ? `${rawError.trim()}\napply_patch expects a raw unified diff patch with lines like:\n--- a/pyservicelab/auth/tokens.py\n+++ b/pyservicelab/auth/tokens.py\n@@ ...\nDo not send prose or only replacement code.\nFallback error: ${fallback.error ?? "unknown"}`
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
