import type { ReactNode } from "react";
import { DashboardShell } from "@/components/dashboard-shell";
import { developerModeService } from "@/modules/developer-mode";

export const dynamic = "force-dynamic";

export default async function DashboardLayout({
  children,
}: {
  children: ReactNode;
}) {
  const developerModeEnabled = await developerModeService.isEnabled();
  return (
    <DashboardShell developerModeEnabled={developerModeEnabled}>
      {children}
    </DashboardShell>
  );
}
