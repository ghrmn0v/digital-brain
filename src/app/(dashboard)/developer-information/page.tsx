import type { Metadata } from "next";
import { DeveloperInformationFeed } from "@/components/developer-information-feed";
import { PageHeader } from "@/components/ui";
import { developerModeService } from "@/modules/developer-mode";

export const metadata: Metadata = { title: "Developer Updates" };

export default async function DeveloperInformationPage() {
  const items = await developerModeService.listInformation(100);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Shared Brain information"
        title="Developer Updates"
        description="Read-only developer findings supplied by Core Brain. This information is available on PC and mobile; no local analysis runs in either client."
      />
      <DeveloperInformationFeed items={items} />
    </div>
  );
}
