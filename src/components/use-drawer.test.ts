import { describe, expect, it } from "vitest";
import { wrapFocus } from "@/components/use-drawer";

/**
 * The suite runs in a node environment with no jsdom, so these stand in for
 * elements with plain objects. `wrapFocus` only ever compares identity and
 * returns one of its inputs, so that is the whole of its contract — and testing
 * it this way is what keeps the awkward cases (empty drawer, single item, focus
 * outside the panel entirely) covered rather than assumed.
 */
const item = (name: string) => ({ name }) as unknown as HTMLElement;
const items = (...names: string[]) => names.map(item);

describe("wrapFocus", () => {
  it("returns null for an empty drawer, so the browser handles Tab", () => {
    expect(wrapFocus([], null, false)).toBeNull();
    expect(wrapFocus([], null, true)).toBeNull();
  });

  it("wraps forwards from the last item to the first", () => {
    const list = items("a", "b", "c");
    expect(wrapFocus(list, list[2], false)).toBe(list[0]);
  });

  it("wraps backwards from the first item to the last", () => {
    const list = items("a", "b", "c");
    expect(wrapFocus(list, list[0], true)).toBe(list[2]);
  });

  it("leaves the ends alone in the direction that still has somewhere to go", () => {
    const list = items("a", "b", "c");
    expect(wrapFocus(list, list[0], false)).toBeNull();
    expect(wrapFocus(list, list[2], true)).toBeNull();
  });

  it("leaves items in the middle alone in both directions", () => {
    const list = items("a", "b", "c");
    expect(wrapFocus(list, list[1], false)).toBeNull();
    expect(wrapFocus(list, list[1], true)).toBeNull();
  });

  it("keeps focus inside a single-item drawer instead of releasing it", () => {
    const only = items("a");
    expect(wrapFocus(only, only[0], false)).toBe(only[0]);
    expect(wrapFocus(only, only[0], true)).toBe(only[0]);
  });

  it("wraps when focus is outside the panel, which is where a stray click leaves it", () => {
    const list = items("a", "b");
    const outside = item("page");
    expect(wrapFocus(list, outside, false)).toBeNull();
    expect(wrapFocus(list, null, false)).toBeNull();
  });

  it("never returns an element that is not in the list it was given", () => {
    const list = items("a", "b", "c", "d");
    for (const active of [list[0], list[1], list[2], list[3], null]) {
      for (const shiftKey of [false, true]) {
        const result = wrapFocus(list, active, shiftKey);
        if (result !== null) expect(list).toContain(result);
      }
    }
  });
});
