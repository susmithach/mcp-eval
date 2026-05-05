// Per-model normalizers live here. When a provider returns unusual patch output
// (JSON-escaped text, etc.) add an entry to MODEL_NORMALIZERS below.

interface ModelNormalizer {
  matches: (providerName: string, model: string) => boolean;
  normalize: (text: string) => string;
}

// Some providers collapse the patch to one line with \n escapes instead of real newlines.
function unescapeJsonEscapes(text: string): string {
  return text
    .replace(/\\\\/g, "\x00") // protect real double-backslashes first
    .replace(/\\n/g, "\n")
    .replace(/\\t/g, "\t")
    .replace(/\\"/g, '"')
    .replace(/\x00/g, "\\");
}

const MODEL_NORMALIZERS: ModelNormalizer[] = [
  {
    // Some OpenAI-compatible models return JSON-escaped patch content.
    matches: (_provider, model) =>
      model.toLowerCase().includes("gpt-oss"),
    normalize: unescapeJsonEscapes,
  },
];

export function extractPatch(
  text: string,
  providerName: string,
  model: string,
): string | null {
  let normalized = text;
  for (const normalizer of MODEL_NORMALIZERS) {
    if (normalizer.matches(providerName, model)) {
      normalized = normalizer.normalize(normalized);
      break;
    }
  }

  const tagged = normalized.match(/<patch>([\s\S]*?)<\/patch>/);
  if (tagged) return tagged[1].trim();

  const fenced = normalized.match(/```(?:diff|patch)?\n([\s\S]*?)\n```/);
  if (fenced) return fenced[1].trim();

  return null;
}
