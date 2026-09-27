import type { Metadata } from "next";
import { ChatApp } from "@/components/chat/chat-app";
import { brainService } from "@/modules/brain";

export const metadata: Metadata = { title: "Chat" };
export const dynamic = "force-dynamic";

/**
 * A full-screen conversation surface, deliberately outside the dashboard
 * layout: chatting is a focused task, not one panel among many.
 */
export default async function ChatPage() {
  const status = await brainService.status();
  return (
    <div className="flex h-full flex-col">
      <ChatApp status={status} />
    </div>
  );
}
