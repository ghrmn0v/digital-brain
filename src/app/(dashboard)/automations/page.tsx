import type { Metadata } from "next";
import { redirect } from "next/navigation";

/* Automations is now a section of /settings. See /approvals for why. */

export const metadata: Metadata = { title: "Automations" };
export default function AutomationsPage() {
  redirect("/settings#automations");
}
