/**
 * Which origins the desktop shell is allowed to load.
 *
 * This is the whole security boundary of the shell, so it lives on its own and
 * is a pure function of its inputs — the main process imports it, and the test
 * suite exercises it directly rather than reading main.js as source text.
 *
 * The rule is deliberately narrower than "not remote". The shell points at a web
 * server on this machine, so the question is not whether the URL is remote but
 * whether it can be made to leave the machine. Only a literal loopback host on
 * an explicitly allowed port qualifies, and the scheme must be plain `http:`:
 * an `https:` loopback would be a different server on a different trust basis,
 * and a non-loopback host — including one that merely *resolves* to 127.0.0.1 —
 * is refused rather than resolved, because a name that can change its answer
 * between the check and the request is exactly how a browser ends up somewhere
 * it was not pointed.
 */

const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]", "::1"]);

export const DEFAULT_PORT = 3000;
export const DEFAULT_TARGET = `http://localhost:${DEFAULT_PORT}`;

/** Modes the shell knows how to open. */
export const SHELL_MODES = /** @type {const} */ (["web", "fly"]);

export class TargetError extends Error {}

/**
 * Resolve the configured target into a validated origin.
 *
 * @param {string | undefined | null} raw   the configured URL, if any
 * @param {number[]} allowedPorts           ports the shell may talk to
 */
export function resolveTarget(raw, allowedPorts = [DEFAULT_PORT]) {
  const value = (raw ?? "").trim() || DEFAULT_TARGET;

  let url;
  try {
    url = new URL(value);
  } catch {
    throw new TargetError(`Not a valid URL: ${value}`);
  }

  if (url.protocol !== "http:") {
    throw new TargetError(`Only http: is allowed, got ${url.protocol}`);
  }

  // hostname drops the brackets from an IPv6 literal, so accept both forms.
  const host = url.hostname.replace(/^\[|\]$/g, "");
  if (!LOOPBACK_HOSTS.has(url.hostname) && !LOOPBACK_HOSTS.has(host)) {
    throw new TargetError(`Not a loopback host: ${url.hostname}`);
  }

  const port = Number(url.port || DEFAULT_PORT);
  if (!allowedPorts.includes(port)) {
    throw new TargetError(
      `Port ${port} is not allowed (expected one of ${allowedPorts.join(", ")})`,
    );
  }

  // Normalised to the origin so string comparison below is exact.
  return { url: url.toString(), origin: url.origin };
}

/** The origin the shell loads, with an explicit fallback if configuration is bad. */
export function safeOrigin(raw, allowedPorts) {
  try {
    return resolveTarget(raw, allowedPorts).origin;
  } catch {
    return new URL(DEFAULT_TARGET).origin;
  }
}

/**
 * Is a URL the shell may navigate to or open a window on?
 *
 * Compared against the origin with `URL.origin`, so a path, query or fragment is
 * irrelevant: `/dashboard`, `/connectome?node=x` and `/` are all the same origin
 * and all allowed, which is what lets the app route internally.
 */
export function isAllowedUrl(candidate, allowedOrigin) {
  let url;
  try {
    url = new URL(candidate);
  } catch {
    return false;
  }
  return url.origin === allowedOrigin;
}

/** Parse the shell mode, defaulting to the web app. */
export function resolveMode(raw) {
  const value = (raw ?? "").trim().toLowerCase();
  return SHELL_MODES.includes(value) ? value : "web";
}
