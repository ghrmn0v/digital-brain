import type { Metadata } from "next";
import { PermissionsManager } from "@/components/permissions-manager";
import { PageHeader } from "@/components/ui";
import { permissionService } from "@/modules/permissions";

export const metadata: Metadata = { title: "Permissions" };

export default async function PermissionsPage() {
  const permissions = await permissionService.list({});

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Action policy"
        title="Permissions"
        description="Control each source and action with explicit automatic, ask-first, or off policies. Disabled entries always resolve to OFF."
      />
      <PermissionsManager permissions={permissions} />
    </div>
  );
}
