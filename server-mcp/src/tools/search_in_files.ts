import * as fs from "fs";
import { z } from "zod";
import {
  assertExists,
  getTargetRepo,
  resolveSafe,
  walkFiles,
} from "../utils/file_utils.js";
import { createLogger } from "../utils/logging.js";

const logger = createLogger("search_in_files");

export const SearchInFilesSchema = z.object({
  query: z.string().min(1, "query must not be empty"),
  path: z.string().min(1, "path must not be empty"),
  limit: z.number().int().min(1).max(500).default(50),
});

export interface SearchMatch {
  file: string;
  line: number;
  content: string;
}

export interface SearchInFilesResult {
  matches: SearchMatch[];
}

const MAX_FILE_READ = 200 * 1024; // 200 KB — skip larger files

export async function searchInFiles(
  rawArgs: unknown
): Promise<SearchInFilesResult> {
  const args = SearchInFilesSchema.parse(rawArgs);
  const base = getTargetRepo();
  const resolved = resolveSafe(base, args.path);

  const start = Date.now();
  try {
    assertExists(resolved);

    const matches: SearchMatch[] = [];
    const query = args.query;

    outer: for (const filePath of walkFiles(resolved)) {
      // Skip binary / oversized files
      let raw: string;
      try {
        const stat = fs.statSync(filePath);
        if (stat.size > MAX_FILE_READ) continue;
        raw = fs.readFileSync(filePath, "utf8");
      } catch {
        continue;
      }

      const lines = raw.split("\n");
      for (let i = 0; i < lines.length; i++) {
        if (lines[i].includes(query)) {
          matches.push({
            file: filePath,
            line: i + 1,
            content: lines[i].trim(),
          });
          if (matches.length >= args.limit) break outer;
        }
      }
    }

    const result: SearchInFilesResult = { matches };
    logger.log(args, Date.now() - start, JSON.stringify(result), true);
    return result;
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    logger.log(args, Date.now() - start, "", false, msg);
    throw err;
  }
}
