import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { createElement } from "react";
import { ChatPanel, renderInlineMarkdown } from "@/components/connectome/chat-panel";

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
