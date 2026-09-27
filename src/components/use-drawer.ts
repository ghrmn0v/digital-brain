"use client";

import { useEffect, useRef, type RefObject } from "react";

const FOCUSABLE =
  "a[href], button:not([disabled]), input, [tabindex]:not([tabindex='-1'])";

/**
 * Where focus should go when Tab or Shift+Tab walks off the end of a drawer.
 *
 * Returns the element to move to, or `null` when the browser's own behaviour is
 * already correct and the event should be left alone. That distinction matters:
 * calling `preventDefault` unconditionally would break Tab for every element in
 * the middle of the list, not just the ends.
 *
 * This is deliberately a pure function of its arguments. It is the only part of
 * the drawer behaviour with real logic in it, and keeping it free of the DOM is
 * what lets it be tested at all — the suite runs in a node environment with no
 * jsdom, so anything that needs `document.activeElement` or a real layout could
 * only ever be verified by hand.
 */
export function wrapFocus(
  focusable: readonly HTMLElement[],
  active: Element | null,
  shiftKey: boolean,
): HTMLElement | null {
  if (focusable.length === 0) return null;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (shiftKey) return active === first ? last : null;
  return active === last ? first : null;
}

/**
 * Overlay focus management, shared by every drawer in the app.
 *
 * A drawer that does not move focus is a drawer keyboard users get stranded
 * behind: Tab walks out into the page they cannot see, and Escape does nothing.
 * This pulls focus in, keeps it inside while the overlay is open, locks the
 * page behind it, and hands focus back to the control that opened it.
 */
export function useDrawer(
  open: boolean,
  close: () => void,
  panelRef: RefObject<HTMLElement | null>,
  toggleRef: RefObject<HTMLElement | null>,
) {
  // Callers pass an inline arrow, so `close` gets a new identity on every
  // render. Depending on it directly would tear this effect down and re-run it
  // on every render, and the cleanup restores focus to the toggle — so any
  // re-render while the drawer was open would yank the user back to the first
  // item mid-navigation. Reading it through a ref keeps it out of the
  // dependencies. The assignment effect is declared first so the ref is already
  // current before the listener below is installed.
  const closeRef = useRef(close);
  useEffect(() => {
    closeRef.current = close;
  });

  useEffect(() => {
    if (!open) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    // Captured now, not in the cleanup, where the ref may already point at a
    // different node.
    const toggle = toggleRef.current;
    const { overflow } = document.body.style;
    document.body.style.overflow = "hidden";

    const focusFirst = window.requestAnimationFrame(() => {
      const target = panelRef.current?.querySelector<HTMLElement>(FOCUSABLE);
      (target ?? panelRef.current)?.focus();
    });

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        closeRef.current();
        return;
      }
      if (event.key !== "Tab" || !panelRef.current) return;
      // `offsetParent` is null for anything not rendered, which keeps hidden and
      // collapsed controls out of the wrap-around order.
      const focusable = [
        ...panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE),
      ].filter((element) => element.offsetParent !== null);
      const target = wrapFocus(focusable, document.activeElement, event.shiftKey);
      if (target) {
        event.preventDefault();
        target.focus();
      }
    };

    document.addEventListener("keydown", onKeyDown);
    return () => {
      window.cancelAnimationFrame(focusFirst);
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = overflow;
      (toggle ?? previouslyFocused)?.focus?.();
    };
  }, [open, panelRef, toggleRef]);
}
