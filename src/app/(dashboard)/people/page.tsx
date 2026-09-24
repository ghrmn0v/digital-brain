import type { Metadata } from "next";
import { IntegrationBoundary } from "@/components/integration-boundary";

export const metadata: Metadata = { title: "People" };

export default function PeoplePage() {
  const configured = Boolean(process.env.CORE_BRAIN_URL?.trim());
  return <IntegrationBoundary kind="people" configured={configured} />;
}
