"use client";

/**
 * Local conversation history for the Brain chat.
 *
 * Kept in the browser on purpose: a chat sidebar must feel instant, and the
 * Brain owns the intelligence, not the transcript. Nothing here reaches the
 * Product API or the Brain until a message is actually sent.
 *
 * Read through `useSyncExternalStore`, never during render, so the React
 * compiler stays happy and the snapshot reference stays stable.
 */

export interface ChatMessage {
  id: string;
  role: "user" | "brain";
  text: string;
  meta?: {
    provider: string | null;
    confidence: number | null;
    grounded: number;
    missing: string[];
    fallback: boolean;
  };
  failed?: boolean;
}

export interface Conversation {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messages: ChatMessage[];
}

const KEY = "product.brain.conversations.v1";
const LIMIT = 50;

let cache: Conversation[] | null = null;
const listeners = new Set<() => void>();

function byNewest(a: Conversation, b: Conversation): number {
  return b.updatedAt - a.updatedAt;
}

function parse(): Conversation[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    return Array.isArray(parsed) ? (parsed as Conversation[]) : [];
  } catch {
    return [];
  }
}

function commit(list: Conversation[]): Conversation[] {
  cache = list;
  if (typeof window !== "undefined") {
    try {
      window.localStorage.setItem(KEY, JSON.stringify(list.slice(0, LIMIT)));
    } catch {
      // A full or disabled store must never break the chat.
    }
  }
  listeners.forEach((listener) => listener());
  return list;
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  window.addEventListener("storage", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}

/** Cached so the reference only changes on an actual mutation. */
export function getSnapshot(): Conversation[] {
  if (cache === null) cache = parse().sort(byNewest);
  return cache;
}

export function newConversation(): Conversation {
  const now = Date.now();
  const suffix = Math.random().toString(36).slice(2, 8);
  return {
    id: `c-${now}-${suffix}`,
    title: "New chat",
    createdAt: now,
    updatedAt: now,
    messages: [],
  };
}

export function saveConversation(conversation: Conversation): Conversation[] {
  return commit(
    [
      conversation,
      ...getSnapshot().filter((item) => item.id !== conversation.id),
    ].sort(byNewest),
  );
}

export function deleteConversation(id: string): Conversation[] {
  return commit(getSnapshot().filter((item) => item.id !== id));
}

export function renameFromFirstMessage(
  conversation: Conversation,
): Conversation {
  if (conversation.title !== "New chat") return conversation;
  const first = conversation.messages.find((message) => message.role === "user");
  if (!first) return conversation;
  const title = first.text.trim().replace(/\s+/g, " ").slice(0, 48);
  return { ...conversation, title: title || "New chat" };
}
