import { z } from "zod";
import { getTargetRepo } from "../utils/file_utils.js";
import { getGitDiff } from "../utils/git_utils.js";
import { createLogger } from "../utils/logging.js";

const logger = createLogger("git_diff");

// No required inputs — empty schema with no required fields
export const GitDiffSchema = z.object({}).strict();

export interface GitDiffResult {
  diff: string;
}

export async function gitDiff(rawArgs: unknown): Promise<GitDiffResult> {
  const _args = GitDiffSchema.parse(rawArgs);
  const repoPath = getTargetRepo();

  const start = Date.now();
  try {
    const diff = await getGitDiff(repoPath);
    const result: GitDiffResult = { diff };

    logger.log({}, Date.now() - start, JSON.stringify(result), true);
    return result;
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    logger.log({}, Date.now() - start, "", false, msg);
    throw err;
  }
}
