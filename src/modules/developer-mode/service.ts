import "server-only";

import { ApiError } from "@/lib/api/errors";
import type { JsonValue, NormalizedEvent } from "@/lib/events";
import {
  DEVELOPER_EVENT_TYPES,
  developerBugDetectedPayloadSchema,
  type DeveloperInformationDto,
  type DeveloperProposalDto,
} from "@/modules/developer-mode/contracts";
import {
  developerModeRepository,
  type DeveloperProposalWithEvent,
} from "@/modules/developer-mode/repository";

function toProposalDto(
  proposal: DeveloperProposalWithEvent,
): DeveloperProposalDto | null {
  const parsed = developerBugDetectedPayloadSchema.safeParse(proposal.event.payload);
  if (!parsed.success) return null;

  return {
    id: proposal.id,
    eventId: proposal.event.eventId,
    repository: parsed.data.repository,
    file: parsed.data.file,
    line: parsed.data.line ?? null,
    column: parsed.data.column ?? null,
    severity: parsed.data.severity,
    title: parsed.data.title,
    message: parsed.data.message,
    context: (parsed.data.context as Record<string, JsonValue> | undefined) ?? null,
    status: proposal.status,
    decidedBy: proposal.decidedBy,
    decisionReason: proposal.decisionReason,
    decidedAt: proposal.decidedAt?.toISOString() ?? null,
    createdAt: proposal.createdAt.toISOString(),
    updatedAt: proposal.updatedAt.toISOString(),
  };
}

export const developerModeService = {
  async isEnabled() {
    return developerModeRepository.isEnabled();
  },

  async setEnabled(enabled: boolean) {
    await developerModeRepository.setEnabled(enabled);
    return { enabled };
  },

  async projectBugDetected(event: NormalizedEvent) {
    if (
      event.source !== "core_brain" ||
      event.type !== "developer.bug_detected"
    ) {
      return null;
    }

    developerBugDetectedPayloadSchema.parse(event.payload);
    const persistedEvent = await developerModeRepository.findEvent(event.id);
    if (!persistedEvent) {
      throw new ApiError(
        409,
        "DEVELOPER_EVENT_NOT_PERSISTED",
        "Developer event was not persisted before projection.",
      );
    }

    return developerModeRepository.upsertProposal(persistedEvent.id);
  },

  async listInformation(limit = 100): Promise<DeveloperInformationDto[]> {
    const events = await developerModeRepository.listInformation(limit);
    return events.map((event) => {
      const proposal = event.developerProposal
        ? toProposalDto({ ...event.developerProposal, event })
        : null;
      return {
        eventId: event.eventId,
        type: event.type as DeveloperInformationDto["type"],
        source: event.source,
        timestamp: event.timestamp.toISOString(),
        receivedAt: event.createdAt.toISOString(),
        payload: event.payload as Record<string, JsonValue>,
        proposal,
      };
    });
  },

  async listProposals(limit = 100) {
    const proposals = await developerModeRepository.listProposals(limit);
    return proposals
      .map(toProposalDto)
      .filter((proposal): proposal is DeveloperProposalDto => proposal !== null);
  },

  async approve(id: string, decidedBy: string, reason?: string) {
    return this.decide(id, "APPROVED", decidedBy, reason);
  },

  async reject(id: string, decidedBy: string, reason?: string) {
    return this.decide(id, "REJECTED", decidedBy, reason);
  },

  async decide(
    id: string,
    status: "APPROVED" | "REJECTED",
    decidedBy: string,
    reason?: string,
  ) {
    if (!(await developerModeRepository.isEnabled())) {
      throw new ApiError(
        409,
        "DEVELOPER_MODE_DISABLED",
        "Developer Mode must be enabled on PC before proposals can be decided.",
      );
    }

    const result = await developerModeRepository.decide(
      id,
      status,
      decidedBy,
      reason,
    );
    if (result.count === 0) {
      throw new ApiError(
        409,
        "DEVELOPER_PROPOSAL_ALREADY_DECIDED",
        "Developer proposal has already been decided.",
      );
    }

    const proposal = await developerModeRepository.findProposal(id);
    if (!proposal) {
      throw new ApiError(
        404,
        "DEVELOPER_PROPOSAL_NOT_FOUND",
        "Developer proposal not found.",
      );
    }
    const dto = toProposalDto(proposal);
    if (!dto) {
      throw new ApiError(
        422,
        "INVALID_DEVELOPER_EVENT",
        "Developer event payload is invalid.",
      );
    }
    return dto;
  },

  supportedEventTypes: DEVELOPER_EVENT_TYPES,
};
