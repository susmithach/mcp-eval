import { buildRagIndex } from "./indexer.js";
import { retrieveRelevantChunks } from "./retriever.js";

interface SmokeQuery {
  label: string;
  query: string;
}

const SMOKE_QUERIES: SmokeQuery[] = [
  {
    label: "task_01",
    query: [
      "task_01 token expiry bypass",
      "tests/test_auth.py::TestTokens::test_decode_expired_token",
      "Token has expired",
      "decode_token expired token",
    ].join("\n"),
  },
  {
    label: "task_09",
    query: [
      "task_09 test count wrong",
      "tests/test_users.py::TestListUsers::test_list_returns_all",
      "assert len(users) == 3",
      "make_user user_a user_b list_users",
    ].join("\n"),
  },
];

function preview(text: string, maxChars = 140): string {
  const normalized = text.replace(/\s+/g, " ").trim();
  if (normalized.length <= maxChars) {
    return normalized;
  }
  return `${normalized.slice(0, maxChars)}...`;
}

const index = await buildRagIndex();
console.log(`Indexed chunks: ${index.chunks.length}`);

for (const smoke of SMOKE_QUERIES) {
  const results = retrieveRelevantChunks(index, smoke.query, { topK: 6 });
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
