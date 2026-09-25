import "server-only";

import { createHash } from "node:crypto";
import { ApiError } from "@/lib/api/errors";
import { prisma } from "@/lib/prisma";
import { Prisma } from "@/generated/prisma/client";

export interface IdempotentResult<T> {
  value: T;
  statusCode: number;
  replayed: boolean;
}

function hashRequest(value: unknown): string {
  return createHash("sha256").update(JSON.stringify(value)).digest("hex");
}

export async function executeIdempotently<T>(options: {
  scope: string;
  key?: string;
  request: unknown;
  operation: () => Promise<{ value: T; statusCode: number }>;
  ttlHours?: number;
}): Promise<IdempotentResult<T>> {
  if (!options.key) {
    const result = await options.operation();
    return { ...result, replayed: false };
  }

  const requestHash = hashRequest(options.request);
  const existing = await prisma.idempotencyRecord.findUnique({
    where: {
      scope_key: { scope: options.scope, key: options.key },
    },
  });

  if (existing) {
    if (existing.expiresAt <= new Date()) {
      await prisma.idempotencyRecord.delete({ where: { id: existing.id } });
    } else {
      if (existing.requestHash !== requestHash) {
        throw new ApiError(
          409,
          "IDEMPOTENCY_KEY_REUSED",
          "Idempotency-Key was already used with a different request.",
        );
      }
      return {
        value: existing.response as T,
        statusCode: existing.statusCode,
        replayed: true,
      };
    }
  }

  const result = await options.operation();
  const expiresAt = new Date(
    Date.now() + (options.ttlHours ?? 24) * 60 * 60 * 1000,
  );

  try {
    await prisma.idempotencyRecord.create({
      data: {
        scope: options.scope,
        key: options.key,
        requestHash,
        statusCode: result.statusCode,
        response: result.value as Prisma.InputJsonValue,
        expiresAt,
      },
    });
  } catch {
    const racedRecord = await prisma.idempotencyRecord.findUnique({
      where: {
        scope_key: { scope: options.scope, key: options.key },
      },
    });
    if (!racedRecord || racedRecord.requestHash !== requestHash) {
      throw new ApiError(
        409,
        "IDEMPOTENCY_CONFLICT",
        "The idempotent request could not be completed.",
      );
    }
    return {
      value: racedRecord.response as T,
      statusCode: racedRecord.statusCode,
      replayed: true,
    };
  }

  return { ...result, replayed: false };
}
