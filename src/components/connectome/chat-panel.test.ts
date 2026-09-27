import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { createElement } from "react";
import {
  ChatPanel,
  describeFallbackReason,
  renderInlineMarkdown,
} from "@/components/connectome/chat-panel";

/**
 * The Brain answers in Markdown, and the panel renders part of it. That is
 * model output being shown to a reader, so the two things worth pinning are:
 * the markers actually become formatting rather than literal asterisks, and
 * text that merely *looks* like markup is still shown as text.
 *
 * These are server-rendered strings on purpose: it keeps the assertion on the
 * produced markup, which is the thing a reader actually sees.
 */

function render(node: React.ReactElement): string {
  return renderToStaticMarkup(node);
}

describe("chat panel markdown handling", () => {
  it("renders a panel without needing a live Brain", () => {
    const html = render(createElement(ChatPanel, {}));
    expect(html).toContain("Ask your brain");
    expect(html).toContain("chat-input");
  });

  it("exposes the question box with a label for assistive technology", () => {
    const html = render(createElement(ChatPanel, {}));
    expect(html).toContain("Ask the Core Brain a question");
  });

  it("keeps an honest empty state rather than a fake answer", () => {
    const html = render(createElement(ChatPanel, {}));
    expect(html).toContain("says so when it could not reach a model");
    // No answer card before anything has been asked.
    expect(html).not.toContain("Confidence 0.");
  });

  it("accepts a context hint without rendering it as markup", () => {
    const html = render(
      createElement(ChatPanel, { initialContext: '<img src=x onerror="alert(1)">' }),
    );
    // The context hint is only held in state, so nothing should be rendered
    // yet - but critically it must not be injected as HTML.
    expect(html).not.toContain("<img src=x");
  });
});

describe("inline markdown rendering", () => {
  it("turns **bold** into a strong element, not literal asterisks", () => {
    const html = renderToStaticMarkup(
      createElement("div", null, renderInlineMarkdown("**Planning Meeting:** tomorrow")),
    );
    expect(html).toContain("<strong");
    expect(html).toContain("Planning Meeting:");
    expect(html).not.toContain("**");
  });

  it("turns `code` into a code element, not literal backticks", () => {
    const html = renderToStaticMarkup(
      createElement("div", null, renderInlineMarkdown("use `npm run build` here")),
    );
    expect(html).toContain("<code");
    expect(html).toContain("npm run build");
    expect(html).not.toContain("`");
  });

  it("leaves plain text untouched", () => {
    const html = renderToStaticMarkup(
      createElement("div", null, renderInlineMarkdown("just a sentence")),
    );
    expect(html).toContain("just a sentence");
    expect(html).not.toContain("<strong");
  });

  it("does not turn model output into HTML", () => {
    const html = renderToStaticMarkup(
      createElement(
        "div",
        null,
        renderInlineMarkdown('<script>alert(1)</script> and <img src=x onerror=y>'),
      ),
    );
    // No raw tag may survive: React escapes every text node, so what was
    // markup in the model output has to still be markup in the document.
    expect(html).not.toContain("<script>");
    expect(html).not.toContain("<img");
    expect(html).toContain("&lt;script&gt;");
  });

  it("handles unpaired and empty markers without throwing", () => {
    for (const input of ["**unclosed", "``", "**", "", "a ** b ** c"]) {
      expect(() => renderToStaticMarkup(
        createElement("div", null, renderInlineMarkdown(input)),
      )).not.toThrow();
    }
  });
});

describe("describeFallbackReason", () => {
  it("translates the quota slug, which is the one worth being specific about", () => {
    // Quota is checked before the generic rate limit on purpose: a quota slug
    // also contains "limit", and "your quota is used up" is a different fact
    // from "slow down".
    expect(
      describeFallbackReason("provider_unavailable:gemini quota exhausted (per-minute limit)"),
    ).toMatch(/quota/i);
    expect(
      describeFallbackReason("provider_unavailable:gemini quota exhausted (per-minute limit)"),
    ).not.toMatch(/rate limit/i);
  });

  it("translates every slug the Brain actually emits", () => {
    const slugs = [
      "provider_unavailable:gemini rate limit reached",
      "provider_unavailable:gemini quota exhausted (per-minute limit)",
      "provider_unavailable:gemini quota exhausted (daily limit)",
      "provider_unavailable:gemini server error (HTTP 503)",
      "provider_unavailable:gemini authentication failed",
      "provider_unavailable:heuristic provider does not support operations…",
      "provider_timeout",
      "provider_error",
    ];
    for (const slug of slugs) {
      const message = describeFallbackReason(slug);
      expect(message, slug).toBeTruthy();
      // A translation must never be the slug wearing different punctuation.
      expect(message, slug).not.toContain("provider_unavailable");
      expect(message, slug).not.toContain("_");
      expect(message, slug).toMatch(/\.$/);
    }
  });

  it("never leaks the raw slug into the sentence shown to a reader", () => {
    for (const slug of [
      "provider_unavailable:gemini quota exhausted (per-minute limit)",
      "provider_unavailable:gemini server error (HTTP 503)",
      "provider_unavailable:heuristic provider does not support operations…",
    ]) {
      const message = describeFallbackReason(slug)!;
      for (const token of slug.split(/[:()…]/).map((t) => t.trim()).filter(Boolean)) {
        // Provider words may legitimately reappear in prose; a slug-shaped
        // fragment may not.
        expect(message.toLowerCase(), `${slug} -> ${message}`).not.toContain(token.toLowerCase().replace(/…$/, ""));
      }
    }
  });

  it("returns null for a missing or unrecognised reason rather than guessing", () => {
    // Inventing a cause is worse than omitting one.
    expect(describeFallbackReason(null)).toBeNull();
    expect(describeFallbackReason("")).toBeNull();
    expect(describeFallbackReason("something_new:who knows")).toBeNull();
  });
});
