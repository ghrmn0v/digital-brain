import type { Metadata } from "next";
import { redirect } from "next/navigation";

/*
 * Approvals is now a section of /settings, not a page of its own.
 *
 * The route stays so that bookmarks, shared links and anything already
 * pointing here still lands somewhere useful: the redirect carries the
 * section, so the reader arrives on the queue rather than at the top of
 * the settings page.
 */

export const metadata: Metadata = { title: "Approvals" };
export default function ApprovalsPage() {
  redirect("/settings#approvals");
}
