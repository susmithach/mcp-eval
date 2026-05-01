/**
 * Centralized patch extraction with a per-model normalizer registry.
 *
 * When a new model produces non-standard output (e.g. JSON-escaped text,
 * markdown wrappers, extra commentary), add one entry to MODEL_NORMALIZERS
 * below. Strategy code never needs to change.
 */

interface ModelNormalizer {
  /** Return true when this normalizer should apply. */
  matches: (providerName: string, model: string) => boolean;
  /** Transform the raw model output before patch extraction. */
  normalize: (text: string) => string;
}

// ---------------------------------------------------------------------------
// Normalizer implementations
// ---------------------------------------------------------------------------

/**
 * Some models output patch content with JSON-style escape sequences
 * (\n, \t, \") instead of literal characters, collapsing all lines into one.
 * Unescape in the correct order to avoid double-processing.
 */
function unescapeJsonEscapes(text: string): string {
  return text
    .replace(/\\\\/g, "\x00") // protect real double-backslashes first
    .replace(/\\n/g, "\n")
    .replace(/\\t/g, "\t")
    .replace(/\\"/g, '"')
    .replace(/\x00/g, "\\");
}

// ---------------------------------------------------------------------------
// Registry — add one entry per model that needs special handling
// ---------------------------------------------------------------------------

const MODEL_NORMALIZERS: ModelNormalizer[] = [
  {
    // gpt-oss-120b on NVIDIA NIM outputs JSON-escaped patch content
    matches: (_provider, model) =>
      model.toLowerCase().includes("gpt-oss"),
    normalize: unescapeJsonEscapes,
  },
];

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Extract a unified-diff patch from raw model output.
 *
 * Applies any registered model-specific normalizer first, then tries:
 *   1. <patch>…</patch> tags
 *   2. ```diff or ```patch fenced code blocks
 *
 * Returns null if no patch is found.
 */
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
