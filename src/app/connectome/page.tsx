import type { Metadata } from "next";
import { prisma } from "@/lib/prisma";
import { connectomeService } from "@/modules/connectome";
import { developerModeService } from "@/modules/developer-mode";
import { ConnectomeWorkspace } from "@/components/connectome/connectome-workspace";

export const metadata: Metadata = { title: "Connectome" };
export const dynamic = "force-dynamic";

/**
 * The Connectome: the app's centre of gravity.
 *
 * It sits outside the dashboard route group on purpose. That group wraps every
 * page in the old sidebar shell, and the point of the Connectome is that it
 * *is* the shell — its own navigation, graph, timeline and inspector in one
 * frame. Nesting it would put a second, competing sidebar around it.
 *
 * The whole graph is read once here and filtered in the browser, so switching
 * source is instant and never re-queries the database mid-interaction.
 *
 * Memories and people still have no read path from the Core Brain, so they stay
 * in the navigation as what they are: a stated boundary, not a populated screen.
 */
export default async function ConnectomePage({
  searchParams,
}: PageProps<"/connectome">) {
  const params = await searchParams;
  const rawNode = Array.isArray(params.node) ? params.node[0] : params.node;

  const [graph, developerModeEnabled, perSource] = await Promise.all([
    connectomeService.graph({ limit: 200 }),
    developerModeService.isEnabled(),
    prisma.integrationEvent.groupBy({
      by: ["source"],
      _count: { _all: true },
      orderBy: { source: "asc" },
    }),
  ]);

  return (
    <ConnectomeWorkspace
      nodes={graph.nodes}
      edges={graph.edges}
      sources={perSource.map((row) => ({
        value: row.source,
        count: row._count._all,
      }))}
      developerModeEnabled={developerModeEnabled}
      initialNodeId={rawNode?.trim() || null}
      now={new Date().toISOString()}
    />
  );
}
