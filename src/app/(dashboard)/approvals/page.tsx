import type { Metadata } from "next";
import { ApprovalsManager } from "@/components/approvals-manager";
import { PageHeader } from "@/components/ui";
import { actionService } from "@/modules/actions";

export const metadata: Metadata = { title: "Approvals" };

export default async function ApprovalsPage() {
  const result = await actionService.list(
    { status: "pending_approval" },
    1,
    100,
  );

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Human-in-the-loop"
        title="AI actions requiring you"
        description="AUTOMATIC actions execute without interrupting you. This queue contains only ASK_FIRST proposals, with structured payloads and a durable decision reason."
      />
      <ApprovalsManager actions={result.items} />
    </div>
  );
}
