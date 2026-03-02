import * as fs from "fs";
import { z } from "zod";
import {
  assertExists,
  assertIsDirectory,
  getTargetRepo,
  resolveSafe,
} from "../utils/file_utils.js";
import { createLogger } from "../utils/logging.js";

const logger = createLogger("list_files");

export const ListFilesSchema = z.object({
  path: z.string().min(1, "path must not be empty"),
});

export interface ListFilesResult {
  files: string[];
  directories: string[];
}

export async function listFiles(rawArgs: unknown): Promise<ListFilesResult> {
  const args = ListFilesSchema.parse(rawArgs);
  const base = getTargetRepo();
  const resolved = resolveSafe(base, args.path);

  const start = Date.now();
  try {
    assertExists(resolved);
    assertIsDirectory(resolved);

    const entries = fs.readdirSync(resolved, { withFileTypes: true });
    const result: ListFilesResult = {
      files: entries.filter((e) => e.isFile()).map((e) => e.name).sort(),
      directories: entries.filter((e) => e.isDirectory()).map((e) => e.name).sort(),
    };

    logger.log(args, Date.now() - start, JSON.stringify(result), true);
    return result;
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    logger.log(args, Date.now() - start, "", false, msg);
    throw err;
  }
}
