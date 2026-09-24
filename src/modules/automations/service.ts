import "server-only";

import { randomUUID } from "node:crypto";
import type { Automation } from "@/generated/prisma/client";
import { ApiError } from "@/lib/api/errors";
import type { JsonObject, JsonValue, NormalizedEvent } from "@/lib/events";
import { actionService } from "@/modules/actions";
import {
  evaluateConditions,
  getValueAtPath,
  type AutomationCondition,
} from "@/modules/automations/condition-evaluator";
import type {
  AutomationCreateInput,
  AutomationDto,
  AutomationListQuery,
  AutomationTriggerKind,
  AutomationUpdateInput,
} from "@/modules/automations/contracts";
import { automationRepository } from "@/modules/automations/repository";

const templatePattern = /\{\{\s*([^{}]+?)\s*\}\}/g;

function toDto(automation: Automation): AutomationDto {
  return {
    id: automation.id,
    name: automation.name,
    description: automation.description,
    enabled: automation.enabled,
    triggerKind: automation.triggerKind.toLowerCase() as AutomationTriggerKind,
    triggerValue: automation.triggerValue,
    conditions: (automation.conditions as unknown as AutomationCondition[]) ?? [],
    action: automation.action,
    actionPayload: (automation.actionPayload as JsonObject) ?? {},
    cooldownSeconds: automation.cooldownSeconds,
    lastRunAt: automation.lastRunAt?.toISOString() ?? null,
    nextRunAt: automation.nextRunAt?.toISOString() ?? null,
    lastError: automation.lastError,
    createdAt: automation.createdAt.toISOString(),
    updatedAt: automation.updatedAt.toISOString(),
  };
}

function assertFound(automation: Automation | null): asserts automation is Automation {
  if (!automation) {
    throw new ApiError(404, "AUTOMATION_NOT_FOUND", "Automation not found.");
  }
}

function resolveStringTemplates(
  value: string,
  context: Record<string, unknown>,
): JsonValue {
  const exact = value.match(/^\{\{\s*([^{}]+?)\s*\}\}$/);
  if (exact) {
    const resolved = getValueAtPath(context, exact[1]);
    if (
      resolved === null ||
      ["string", "number", "boolean"].includes(typeof resolved)
    ) {
      return resolved as JsonValue;
    }
    if (Array.isArray(resolved) || (resolved && typeof resolved === "object")) {
      return resolved as JsonValue;
    }
  }

  return value.replace(templatePattern, (_match, path: string) => {
    const resolved = getValueAtPath(context, path);
    return resolved === undefined || resolved === null
      ? ""
      : typeof resolved === "object"
        ? JSON.stringify(resolved)
        : String(resolved);
  });
}

function resolveTemplates(
  value: JsonValue,
  context: Record<string, unknown>,
): JsonValue {
  if (typeof value === "string") return resolveStringTemplates(value, context);
  if (Array.isArray(value)) {
    return value.map((item) => resolveTemplates(item, context));
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [
        key,
        resolveTemplates(item, context),
      ]),
    );
  }
  return value;
}

function eventContext(event: NormalizedEvent): Record<string, unknown> {
  return {
    event: {
      id: event.id,
      source: event.source,
      type: event.type,
      timestamp: event.timestamp,
      payload: event.payload,
      metadata: event.metadata ?? null,
    },
  };
}

async function runAutomation(
  automation: Automation,
  context: Record<string, unknown>,
  eventId?: string,
) {
  const run = await automationRepository.createRun({
    automation: { connect: { id: automation.id } },
    eventId,
    status: "PENDING",
  });
  const actionPayload = resolveTemplates(
    (automation.actionPayload as JsonValue) ?? {},
    {
      ...context,
      automation: { id: automation.id, name: automation.name },
    },
  );

  try {
    const response = await actionService.request(
      {
        id: randomUUID(),
        source: "automation",
        action: automation.action,
        payload:
          actionPayload && typeof actionPayload === "object" && !Array.isArray(actionPayload)
            ? actionPayload
            : {},
        requestedAt: new Date().toISOString(),
        correlationId: eventId,
      },
      `automation:${run.id}`,
    );
    await automationRepository.attachActionExecution(run.id, response.actionId);

    if (response.status === "completed") {
      await automationRepository.completeRun(run.id, "COMPLETED");
    } else if (response.status === "rejected") {
      await automationRepository.completeRun(
        run.id,
        "REJECTED",
        response.error,
      );
    } else if (response.status === "failed") {
      await automationRepository.completeRun(run.id, "FAILED", response.error);
    }

    await automationRepository.markTriggered(
      automation.id,
      response.status === "failed" ? response.error : undefined,
    );
    return response;
  } catch (error) {
    const message =
      error instanceof ApiError ? error.message : "Automation action failed.";
    await automationRepository.completeRun(run.id, "FAILED", message);
    await automationRepository.markTriggered(automation.id, message);
    throw error;
  }
}

function cooldownActive(automation: Automation, now: Date): boolean {
  if (!automation.cooldownSeconds || !automation.lastRunAt) return false;
  return (
    automation.lastRunAt.getTime() + automation.cooldownSeconds * 1_000 >
    now.getTime()
  );
}

export const automationService = {
  async list(query: AutomationListQuery) {
    return (await automationRepository.list(query)).map(toDto);
  },

  async get(id: string) {
    const automation = await automationRepository.findById(id);
    assertFound(automation);
    return toDto(automation);
  },

  async create(input: AutomationCreateInput) {
    return toDto(await automationRepository.create(input));
  },

  async update(id: string, input: AutomationUpdateInput) {
    const current = await automationRepository.findById(id);
    assertFound(current);
    const triggerKind = input.triggerKind ?? current.triggerKind.toLowerCase();
    const nextRunAt =
      input.nextRunAt === undefined
        ? current.nextRunAt?.toISOString()
        : input.nextRunAt;
    if (triggerKind === "schedule" && !nextRunAt) {
      throw new ApiError(
        400,
        "AUTOMATION_SCHEDULE_REQUIRED",
        "Schedule automations require nextRunAt.",
      );
    }
    return toDto(await automationRepository.update(id, input));
  },

  async remove(id: string) {
    const current = await automationRepository.findById(id);
    assertFound(current);
    await automationRepository.delete(id);
  },

  async runManually(id: string) {
    const automation = await automationRepository.findById(id);
    assertFound(automation);
    return runAutomation(automation, {
      manual: { triggeredAt: new Date().toISOString(), automationId: id },
    });
  },

  async processEvent(event: NormalizedEvent) {
    const automations = await automationRepository.listEventAutomations(event.type);
    const now = new Date();
    const context = eventContext(event);

    for (const automation of automations) {
      if (cooldownActive(automation, now)) {
        const skipped = await automationRepository.createRun({
          automation: { connect: { id: automation.id } },
          eventId: event.id,
          status: "SKIPPED",
          completedAt: now,
        });
        await automationRepository.completeRun(
          skipped.id,
          "SKIPPED",
          "Cooldown is active.",
        );
        continue;
      }

      const conditions = (automation.conditions as unknown as AutomationCondition[]) ?? [];
      if (!evaluateConditions(context, conditions)) {
        const skipped = await automationRepository.createRun({
          automation: { connect: { id: automation.id } },
          eventId: event.id,
          status: "SKIPPED",
          completedAt: now,
        });
        await automationRepository.completeRun(
          skipped.id,
          "SKIPPED",
          "Conditions did not match.",
        );
        continue;
      }

      await runAutomation(automation, context, event.id);
    }
  },

  async processSchedules(now = new Date()) {
    const automations = await automationRepository.listDueSchedules(now);
    for (const automation of automations) {
      await automationRepository.clearSchedule(automation.id);
      await runAutomation(automation, {
        schedule: { scheduledAt: automation.nextRunAt?.toISOString() ?? now.toISOString() },
      });
    }
    return { processed: automations.length };
  },
};
