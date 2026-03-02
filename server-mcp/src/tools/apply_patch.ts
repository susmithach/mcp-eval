import { z } from "zod";
import { getTargetRepo } from "../utils/file_utils.js";
import { applyGitPatch } from "../utils/git_utils.js";
import { createLogger } from "../utils/logging.js";

const logger = createLogger("apply_patch");

export const ApplyPatchSchema = z.object({
  patch: z.string().min(1, "patch must not be empty"),
});

export interface ApplyPatchResult {
  applied: boolean;
  error: string | null;
}

export async function applyPatch(rawArgs: unknown): Promise<ApplyPatchResult> {
  const args = ApplyPatchSchema.parse(rawArgs);
  const repoPath = getTargetRepo();

  const start = Date.now();
  try {
    const patchBytes = Buffer.byteLength(args.patch, "utf8");
    const result = await applyGitPatch(repoPath, args.patch);

    logger.log(
      { patchSizeBytes: patchBytes },
      Date.now() - start,
      JSON.stringify(result),
      result.applied
    );
    return result;
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    logger.log(args, Date.now() - start, "", false, msg);
    throw err;
  }
}
