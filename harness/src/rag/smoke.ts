import { buildRagIndex } from "./indexer.js";
import { retrieveRelevantChunks } from "./retriever.js";

interface SmokeQuery {
  label: string;
  query: string;
}

const PRESET_QUERIES: Record<string, SmokeQuery> = {
  task_01: {
    label: "task_01",
    query: [
      "task_01 token expiry bypass",
      "tests/test_auth.py::TestTokens::test_decode_expired_token",
      "Token has expired",
      "decode_token expired token",
    ].join("\n"),
  },
  task_02: {
    label: "task_02",
    query: [
      "task_02 project tags inverted",
      "tests/test_projects.py::TestCreateProject::test_create_with_tags",
      "tests/test_projects.py::TestUpdateProject::test_update_tags",
      "tags get_tags split comma empty tokens",
    ].join("\n"),
  },
  task_09: {
    label: "task_09",
    query: [
      "task_09 test count wrong",
      "tests/test_users.py::TestListUsers::test_list_returns_all",
      "assert len(users) == 3",
      "make_user user_a user_b list_users",
    ].join("\n"),
  },
};

function parseArgs(): { queries: SmokeQuery[]; topK: number } {
  const topKArg = process.argv.find((arg) => arg.startsWith("--topk="));
  const topK = topKArg ? Number.parseInt(topKArg.split("=")[1] ?? "", 10) : 6;
  if (!Number.isFinite(topK) || topK < 1) {
    throw new Error("Invalid --topk value; must be a positive integer");
  }

  const taskArg = process.argv.find((arg) => arg.startsWith("--task="));
  const queryArg = process.argv.find((arg) => arg.startsWith("--query="));
  const labelArg = process.argv.find((arg) => arg.startsWith("--label="));

  if (queryArg) {
    return {
      topK,
      queries: [
        {
          label: labelArg ? labelArg.split("=")[1] ?? "custom" : "custom",
          query: queryArg.split("=").slice(1).join("="),
        },
      ],
    };
  }

  if (taskArg) {
    const taskId = taskArg.split("=")[1] ?? "";
    const preset = PRESET_QUERIES[taskId];
    if (!preset) {
      const available = Object.keys(PRESET_QUERIES).sort().join(", ");
      throw new Error(
        `Unknown --task value "${taskId}". Available presets: ${available}`,
      );
    }
    return { topK, queries: [preset] };
  }

  return {
    topK,
    queries: Object.keys(PRESET_QUERIES)
      .sort()
      .map((key) => PRESET_QUERIES[key]),
  };
}

function preview(text: string, maxChars = 140): string {
  const normalized = text.replace(/\s+/g, " ").trim();
  if (normalized.length <= maxChars) {
    return normalized;
  }
  return `${normalized.slice(0, maxChars)}...`;
}

const { queries, topK } = parseArgs();
const index = await buildRagIndex();
console.log(`Indexed chunks: ${index.chunks.length}`);

for (const smoke of queries) {
  const results = retrieveRelevantChunks(index, smoke.query, { topK });
  console.log(`\n=== ${smoke.label} ===`);
  if (results.length === 0) {
    console.log("(no results)");
    continue;
  }

  for (const [idx, item] of results.entries()) {
    console.log(
      `${idx + 1}. score=${item.score.toFixed(4)} ${item.chunk.path}:${item.chunk.startLine}-${item.chunk.endLine}`,
    );
    console.log(`   ${preview(item.chunk.text)}`);
  }
}
