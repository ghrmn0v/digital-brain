import type { ReactNode } from "react";

export const metadata = { title: "Chat" };

/** Full-viewport shell with no dashboard chrome. */
export default function ChatLayout({ children }: { children: ReactNode }) {
  return <div className="h-dvh overflow-hidden bg-[#1a1a1a]">{children}</div>;
}
