import "server-only";

import { randomUUID } from "node:crypto";
import { ZodError } from "zod";
import type { ActionExecution } from "@/generated/prisma/client";
import { Prisma } from "@/generated/prisma/client";
import { ApiError } from "@/lib/api/errors";
import {
  actionRequestSchema,
  type ActionRequest,
  type ActionResponse,
  type ActionStatus,
} from "@/lib/actions";
import type { JsonObject, JsonValue } from "@/lib/events";
import { PRODUCT_EVENTS, eventBus } from "@/lib/events/event-bus";
import type { ActionExecutionDto } from "@/modules/actions/contracts";
import {
  createNormalizedEvent,
  integrationEventService,
} from "@/modules/events";
import { actionExecutionRepository } from "@/modules/actions/repository";
import {
  actionHandlers,
  type ActionHandler,
} from "@/modules/actions/registry";
import { permissionService } from "@/modules/permissions";

function toStatus(status: ActionExecution["status"]): ActionStatus {
  return status.toLowerCase() as ActionStatus;
}

function toDto(execution: ActionExecution): ActionExecutionDto {
  return {
    id: execution.id,
    source: execution.source,
    action: execution.action,
    payload: execution.payload as Record<string, unknown>,
    status: toStatus(execution.status),
    permissionLevel: execution.permissionLevel,
    idempotencyKey: execution.idempotencyKey,
    correlationId: execution.correlationId,
    result: (execution.result as JsonValue | null) ?? null,
    error: execution.error,
    decidedBy: execution.decidedBy,
    decisionReason: execution.decisionReason,
    attempts: execution.attempts,
    requestedAt: execution.requestedAt.toISOString(),
    decidedAt: execution.decidedAt?.toISOString() ?? null,
    completedAt: execution.completedAt?.toISOString() ?? null,
    createdAt: execution.createdAt.toISOString(),
    updatedAt: execution.updatedAt.toISOString(),
  };
}

function toResponse(execution: ActionExecution): ActionResponse {
  const status = toStatus(execution.status);
  return {
    actionId: execution.id,
    success: execution.status === "COMPLETED",
    status,
    ...(execution.result !== null
      ? { result: execution.result as JsonValue }
      : {}),
    ...(execution.error ? { error: execution.error } : {}),
  };
}

function publicExecutionError(error: unknown): string {
  if (error instanceof ZodError) return "Action payload is invalid.";
  if (error instanceof ApiError) return error.message;
  return "Action execution failed.";
}

async function emitResponse(response: ActionResponse) {
  await eventBus.emit(PRODUCT_EVENTS.ACTION_RESPONSE, response);

  const event = createNormalizedEvent({
    source: "system",
    type: "action.response",
    id: `action-response-${response.actionId}-${response.status}`,
    payload: {
      actionId: response.actionId,
      success: response.success,
      status: response.status,
      result: response.result ?? null,
      error: response.error ?? null,
    },
    metadata: { correlationId: response.actionId },
  });

  try {
    await integrationEventService.publish(event, ["core_brain", "fly"]);
  } catch (error) {
    console.error("Action response event could not be persisted.", {
      actionId: response.actionId,
      error,
    });
  }
}

export const actionService = {
  async list(
    query: Parameters<typeof actionExecutionRepository.list>[0],
    page: number,
    limit: number,
  ) {
    const { items, total } = await actionExecutionRepository.list(query, page, limit);
    return {
      items: items.map(toDto),
      pagination: {
        page,
        limit,
        total,
        totalPages: Math.ceil(total / limit),
      },
    };
  },

  async get(id: string) {
    const execution = await actionExecutionRepository.findById(id);
    if (!execution) {
      throw new ApiError(404, "ACTION_NOT_FOUND", "Action execution not found.");
    }
    return toDto(execution);
  },

  async request(input: unknown, idempotencyKey?: string) {
    const parsed = actionRequestSchema.parse(input);
    const handler = actionHandlers[parsed.action];
    if (!handler) {
      throw new ApiError(400, "ACTION_NOT_SUPPORTED", "Action is not supported.");
    }

    if (idempotencyKey) {
      const existing = await actionExecutionRepository.findByIdempotencyKey(
        idempotencyKey,
      );
      if (existing) return toResponse(existing);
    }

    const request: ActionRequest = {
      id: parsed.id ?? randomUUID(),
      source: parsed.source,
      action: parsed.action,
      payload: parsed.payload,
      requestedAt: parsed.requestedAt ?? new Date().toISOString(),
      correlationId: parsed.correlationId,
    };
    await eventBus.emit(PRODUCT_EVENTS.ACTION_REQUESTED, request);

    const decision = await permissionService.resolve(request.source, request.action);
    let execution: ActionExecution;

    if (decision.level === "OFF") {
      execution = await actionExecutionRepository.create({
        id: request.id,
        source: request.source,
        action: request.action,
        payload: request.payload as Prisma.InputJsonValue,
        status: "REJECTED",
        permissionLevel: decision.level,
        idempotencyKey,
        correlationId: request.correlationId,
        error: decision.reason ?? "Action is disabled by permission policy.",
        requestedAt: new Date(request.requestedAt),
        decidedAt: new Date(),
        completedAt: new Date(),
      });
      await actionExecutionRepository.syncAutomationRun(
        execution.id,
        "REJECTED",
        execution.error ?? undefined,
      );
    } else if (decision.level === "ASK_FIRST") {
      execution = await actionExecutionRepository.create({
        id: request.id,
        source: request.source,
        action: request.action,
        payload: request.payload as Prisma.InputJsonValue,
        status: "PENDING_APPROVAL",
        permissionLevel: decision.level,
        idempotencyKey,
        correlationId: request.correlationId,
        requestedAt: new Date(request.requestedAt),
      });
    } else {
      execution = await actionExecutionRepository.create({
        id: request.id,
        source: request.source,
        action: request.action,
        payload: request.payload as Prisma.InputJsonValue,
        status: "PENDING_APPROVAL",
        permissionLevel: decision.level,
        idempotencyKey,
        correlationId: request.correlationId,
        requestedAt: new Date(request.requestedAt),
      });
      execution = await this.execute(execution, handler);
    }

    const response = toResponse(execution);
    await emitResponse(response);
    return response;
  },

  async approve(id: string, decidedBy: string, reason?: string) {
    const execution = await actionExecutionRepository.findById(id);
    if (!execution) {
      throw new ApiError(404, "ACTION_NOT_FOUND", "Action execution not found.");
    }
    if (execution.status !== "PENDING_APPROVAL") {
      throw new ApiError(409, "ACTION_ALREADY_DECIDED", "Action is already decided.");
    }

    const decision = await permissionService.resolve(execution.source, execution.action);
    if (decision.level === "OFF") {
      const rejected = await actionExecutionRepository.markRejected(id, {
        permissionLevel: decision.level,
        decidedBy,
        decisionReason: reason ?? decision.reason,
      });
      await actionExecutionRepository.syncAutomationRun(
        rejected.id,
        "REJECTED",
        rejected.error ?? undefined,
      );
      const response = toResponse(rejected);
      await emitResponse(response);
      return response;
    }

    const claimed = await actionExecutionRepository.claimPending(id, execution.version, {
      decidedBy,
      decisionReason: reason,
    });
    if (claimed.count === 0) {
      throw new ApiError(409, "ACTION_ALREADY_DECIDED", "Action is already decided.");
    }

    const handler = actionHandlers[execution.action];
    if (!handler) {
      throw new ApiError(400, "ACTION_NOT_SUPPORTED", "Action is not supported.");
    }
    const completed = await this.execute(
      {
        ...execution,
        decidedBy,
        decisionReason: reason ?? null,
        version: execution.version + 1,
      },
      handler,
    );
    const response = toResponse(completed);
    await emitResponse(response);
    return response;
  },

  async reject(id: string, decidedBy: string, reason?: string) {
    const execution = await actionExecutionRepository.findById(id);
    if (!execution) {
      throw new ApiError(404, "ACTION_NOT_FOUND", "Action execution not found.");
    }
    const result = await actionExecutionRepository.rejectPending(
      id,
      execution.version,
      { decidedBy, decisionReason: reason },
    );
    if (result.count === 0) {
      throw new ApiError(409, "ACTION_ALREADY_DECIDED", "Action is already decided.");
    }
    const rejected = await actionExecutionRepository.findById(id);
    if (!rejected) {
      throw new ApiError(404, "ACTION_NOT_FOUND", "Action execution not found.");
    }
    await actionExecutionRepository.syncAutomationRun(
      rejected.id,
      "REJECTED",
      rejected.error ?? undefined,
    );
    const response = toResponse(rejected);
    await emitResponse(response);
    return response;
  },

  async execute(execution: ActionExecution, handler: ActionHandler) {
    const attempts = execution.attempts + 1;
    try {
      const result = await handler(execution.payload as JsonObject, {
        executionId: execution.id,
        source: execution.source,
      });
      const completed = await actionExecutionRepository.complete(
        execution.id,
        result as Prisma.InputJsonValue,
        attempts,
      );
      await actionExecutionRepository.syncAutomationRun(
        execution.id,
        "COMPLETED",
      );
      return completed;
    } catch (error) {
      console.error("Action execution failed.", {
        actionId: execution.id,
        action: execution.action,
        error,
      });
      const publicError = publicExecutionError(error);
      const failed = await actionExecutionRepository.fail(
        execution.id,
        publicError,
        attempts,
      );
      await actionExecutionRepository.syncAutomationRun(
        execution.id,
        "FAILED",
        publicError,
      );
      return failed;
    }
  },
};
