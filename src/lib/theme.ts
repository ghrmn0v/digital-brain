"use client";

/**
 * Theme state lives on the `<html data-theme>` attribute, so one flip repaints
 * every screen through the CSS variables.
 *
 * Read with `useSyncExternalStore` rather than an effect, so there is no
 * cascading render and no storage access during render.
 */

export type Theme = "light" | "dark";

const EVENT = "product:theme";

function current(): Theme {
  if (typeof document === "undefined") return "light";
  return document.documentElement.getAttribute("data-theme") === "dark"
    ? "dark"
    : "light";
}

export function subscribeTheme(listener: () => void): () => void {
  window.addEventListener(EVENT, listener);
  window.addEventListener("storage", listener);
  return () => {
    window.removeEventListener(EVENT, listener);
    window.removeEventListener("storage", listener);
  };
}

export function getTheme(): Theme {
  return current();
}

export function getServerTheme(): Theme {
  return "light";
}

export function setTheme(theme: Theme): void {
  document.documentElement.setAttribute("data-theme", theme);
  try {
    window.localStorage.setItem("product.theme", theme);
  } catch {
    // A disabled store just means the choice is not remembered.
  }
  window.dispatchEvent(new Event(EVENT));
}
