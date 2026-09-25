// Pure helpers for the Developer Mode thought bubble and Fly anchoring.
// Core Brain owns all text; these functions only arrange what it sent — never generate it.

export const DEFAULT_BUBBLE_MS = 7000;

function locationLine(dev) {
  const path = [dev.repository, dev.file].filter(Boolean).join(" / ");
  if (!path) return "";
  let line = "";
  if (Number.isFinite(dev.line)) {
    line = `:${dev.line}`;
    if (Number.isFinite(dev.column)) line += `:${dev.column}`;
  }
  return `${path}${line}`;
}

export function resolveDeveloperBubble(context) {
  const dev = context && context.developer;
  if (!dev) return null;
  const severity = (dev.severity || "info").toLowerCase();
  const title = dev.title || dev.type || "developer event";
  return {
    speaker: `${severity.toUpperCase()} · ${title}`,
    text: dev.message, // verbatim from Core Brain, displayed unchanged
    meta: locationLine(dev),
    durationMs: Number.isFinite(dev.bubble_ms) ? dev.bubble_ms : DEFAULT_BUBBLE_MS,
  };
}

export function anchorFor(context) {
  const anchor = context && context.developer && context.developer.anchor;
  return typeof anchor === "string" && anchor.length > 0 ? anchor : null;
}
