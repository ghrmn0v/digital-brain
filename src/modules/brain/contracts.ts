import { z } from "zod";

/**
 * Product-side view of the Core Brain connection.
 *
 * Product owns no intelligence. It only knows how to reach the Brain, which
 * methods exist, and how to render what the Brain returns. Every value here is
 * either configuration or a pass-through of a Brain contract — never invented.
 */

export const BRAIN_USER_ID = z
  .string()
  .min(1)
  .max(512)
  .default("usr_owner");

export const brainChatInputSchema = z
  .object({
    message: z.string().trim().min(1).max(8_000),
    sessionId: z.string().min(1).max(256).optional(),
    recordLearning: z.boolean().default(true),
  })
  .strict();

export const brainSearchInputSchema = z
  .object({
    text: z.string().trim().max(2_000).optional(),
    limit: z.number().int().min(1).max(50).default(10),
    importanceMin: z.number().min(0).max(1).optional(),
  })
  .strict();

export const brainUnderstandInputSchema = z
  .object({
    corpus: z.string().trim().min(1).max(50_000),
  })
  .strict();

export const brainResolvePersonInputSchema = z
  .object({
    name: z.string().trim().min(1).max(200),
    aliases: z.array(z.string().trim().min(1).max(200)).max(10).default([]),
  })
  .strict();

export const brainIngestInputSchema = z
  .object({
    type: z
      .string()
      .regex(/^source\.[a-z0-9_]+(\.[a-z0-9_]+)+$/, "Must be a source.* event type"),
    provider: z.string().trim().min(1).max(64),
    payload: z.record(z.string(), z.json()).default({}),
    personName: z.string().trim().min(1).max(200).optional(),
    occurredAt: z.iso.datetime({ offset: true }).optional(),
  })
  .strict()
  .superRefine((value, ctx) => {
    const rule = SUPPORTED_SOURCE_EVENTS.find((entry) => entry.type === value.type);
    if (rule) {
      if (rule.required !== "no fields" && !(rule.required in value.payload)) {
        ctx.addIssue({
          code: "custom",
          path: ["payload", rule.required],
          message: `The Brain requires "${rule.required}" for ${rule.type}.`,
        });
      }
      return;
    }
    ctx.addIssue({
      code: "custom",
      path: ["type"],
      message:
        "No mapping rule exists for this type, so the Brain will store the event but create no memory. Pick one of the listed event types.",
    });
  });

export const brainReasonInputSchema = z
  .object({
    task: z.string().trim().min(1).max(2_000).optional(),
    repository: z.string().trim().min(1).max(512).default("digital-brain-product"),
    filePath: z.string().trim().min(1).max(1_024).default("src/example.ts"),
    content: z.string().max(50_000).default(""),
    language: z.string().trim().max(64).default("typescript"),
  })
  .strict();

export const brainPreferenceInputSchema = z
  .object({
    preference: z.string().trim().min(1).max(200),
    value: z.string().trim().max(2_000).default(""),
    domain: z.string().trim().max(64).optional(),
  })
  .strict();

/** A single Brain capability as shown in the Product UI. */
export interface BrainCapabilityDto {
  readonly method: string;
  readonly group: BrainCapabilityGroup;
  readonly summary: string;
  readonly interactive: boolean;
}

export type BrainCapabilityGroup =
  | "converse"
  | "understand"
  | "memory"
  | "people"
  | "preferences"
  | "developer"
  | "ingest"
  | "system";

/**
 * The Brain only turns a normalized source event into memory when a
 * `(provider, action)` mapping rule exists. These are the built-in rules, so the
 * UI can offer them instead of letting the user guess and get
 * "no mapping rule for ..." back.
 */
export const SUPPORTED_SOURCE_EVENTS = [
  {
    type: "source.linkedin.profile_updated",
    provider: "linkedin",
    label: "LinkedIn profile update",
    memoryType: "fact",
    required: "no fields",
  },
  {
    type: "source.linkedin.job_seen",
    provider: "linkedin",
    label: "LinkedIn job seen",
    memoryType: "fact",
    required: "company",
  },
  {
    type: "source.calendar.event_created",
    provider: "calendar",
    label: "Calendar event",
    memoryType: "event",
    required: "summary",
  },
  {
    type: "source.whatsapp.message_received",
    provider: "whatsapp",
    label: "WhatsApp message",
    memoryType: "interaction",
    required: "text",
  },
  {
    type: "source.todo.task_created",
    provider: "todo",
    label: "Task created",
    memoryType: "episode",
    required: "description",
  },
] as const satisfies readonly {
  type: string;
  provider: string;
  label: string;
  memoryType: string;
  required: string;
}[];

export interface BrainStatusDto {
  readonly reachable: boolean;
  readonly url: string | null;
  readonly apiVersion: string | null;
  readonly service: string | null;
  readonly provider: string | null;
  readonly methodCount: number;
  readonly capabilities: readonly BrainCapabilityDto[];
  readonly error: string | null;
}
