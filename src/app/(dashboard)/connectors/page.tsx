import type { Metadata } from "next";
import { redirect } from "next/navigation";

/* Connectors is now a section of /settings. See /approvals for why. */

export const metadata: Metadata = { title: "Connectors" };
export default function ConnectorsPage() {
  redirect("/settings#connectors");
}
