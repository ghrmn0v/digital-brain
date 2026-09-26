import type { Metadata } from "next";
import { ChatView } from "@/components/connectome/chat-view";

export const metadata: Metadata = { title: "Chat" };

/**
 * Chat lives outside the dashboard route group, like the Connectome, because it
 * is a full-frame surface rather than a card on a page. It shares the
 * Connectome's navigation so the two sit in one application.
 */
export default function ChatPage() {
  return <ChatView />;
}
