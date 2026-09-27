import type { Metadata } from "next";
import { redirect } from "next/navigation";

/* Permissions is now a section of /settings. See /approvals for why. */

export const metadata: Metadata = { title: "Permissions" };
export default function PermissionsPage() {
  redirect("/settings#permissions");
}
