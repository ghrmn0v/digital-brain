import { redirect } from "next/navigation";

/**
 * `/connections` is a name people reach for, and it used to 404.
 *
 * Everything it would mean — which services are up, what the workspace is
 * allowed to do — is already on `/permissions`, which shows the Brain transport,
 * the Fly engine, local storage, the desktop shell and the policy mix. Rather
 * than keep two pages that drift apart, this maps to it permanently so the URL
 * works and there is one source of truth.
 */
export default function ConnectionsPage() {
  redirect("/permissions");
}
