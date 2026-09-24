import type { Metadata } from "next";
import { IntegrationBoundary } from "@/components/integration-boundary";

export const metadata: Metadata = { title: "Memory" };

export default function MemoryPage() {
  const configured = Boolean(process.env.CORE_BRAIN_URL?.trim());
  return <IntegrationBoundary kind="memory" configured={configured} />;
}
