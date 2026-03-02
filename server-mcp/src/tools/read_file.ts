import * as fs from "fs";
import { z } from "zod";
import {
  assertExists,
  assertIsFile,
  getFileSize,
  getTargetRepo,
  MAX_FILE_SIZE,
  resolveSafe,
} from "../utils/file_utils.js";
import { createLogger } from "../utils/logging.js";

const logger = createLogger("read_file");

export const ReadFileSchema = z.object({
  path: z.string().min(1, "path must not be empty"),
});

export interface ReadFileResult {
  content: string;
  size: number;
}

export async function readFile(rawArgs: unknown): Promise<ReadFileResult> {
  const args = ReadFileSchema.parse(rawArgs);
  const base = getTargetRepo();
  const resolved = resolveSafe(base, args.path);

  const start = Date.now();
  try {
    assertExists(resolved);
    assertIsFile(resolved);

    const size = getFileSize(resolved);
    if (size > MAX_FILE_SIZE) {
      throw new Error(
        `File too large: ${size} bytes (limit ${MAX_FILE_SIZE} bytes / 200 KB)`
      );
    }

    const content = fs.readFileSync(resolved, "utf8");
    const result: ReadFileResult = { content, size };

    logger.log(args, Date.now() - start, JSON.stringify(result), true);
    return result;
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    logger.log(args, Date.now() - start, "", false, msg);
    throw err;
  }
}
