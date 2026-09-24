import type { Metadata } from "next";
import { AutomationsManager } from "@/components/automations-manager";
import { PageHeader } from "@/components/ui";
import { automationService } from "@/modules/automations";

export const metadata: Metadata = { title: "Automations" };

export default async function AutomationsPage() {
  const automations = await automationService.list({});

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Event workflows"
        title="Automations"
        description="Translate normalized events into registered actions with explicit JSON payloads, optional conditions, and human permission enforcement."
      />
      <AutomationsManager automations={automations} />
    </div>
  );
}
