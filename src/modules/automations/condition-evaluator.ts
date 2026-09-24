import type { JsonValue } from "@/lib/events";

export type ConditionOperator =
  | "eq"
  | "neq"
  | "contains"
  | "not_contains"
  | "gt"
  | "gte"
  | "lt"
  | "lte"
  | "exists"
  | "in";

export interface AutomationCondition {
  path: string;
  operator: ConditionOperator;
  value?: JsonValue;
}

const blockedSegments = new Set(["__proto__", "prototype", "constructor"]);

export function getValueAtPath(
  input: Record<string, unknown>,
  path: string,
): unknown {
  const segments = path.split(".");
  if (
    segments.length === 0 ||
    segments.length > 12 ||
    segments.some((segment) => !segment || blockedSegments.has(segment))
  ) {
    return undefined;
  }

  let current: unknown = input;
  for (const segment of segments) {
    if (current === null || typeof current !== "object") return undefined;
    if (Array.isArray(current)) {
      const index = Number(segment);
      if (!Number.isInteger(index) || index < 0) return undefined;
      current = current[index];
    } else {
      current = (current as Record<string, unknown>)[segment];
    }
  }
  return current;
}

function comparableNumber(value: unknown): number | null {
  if (typeof value === "number") return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

export function evaluateCondition(
  root: Record<string, unknown>,
  condition: AutomationCondition,
): boolean {
  const actual = getValueAtPath(root, condition.path);

  switch (condition.operator) {
    case "exists":
      return condition.value === false ? actual === undefined : actual !== undefined;
    case "eq":
      return actual === condition.value;
    case "neq":
      return actual !== condition.value;
    case "contains":
      return typeof actual === "string" && typeof condition.value === "string"
        ? actual.includes(condition.value)
        : Array.isArray(actual) &&
            condition.value !== undefined &&
            actual.some((item) => item === condition.value);
    case "not_contains":
      return typeof actual === "string" && typeof condition.value === "string"
        ? !actual.includes(condition.value)
        : Array.isArray(actual) &&
            condition.value !== undefined &&
            !actual.some((item) => item === condition.value);
    case "gt": {
      const left = comparableNumber(actual);
      const right = comparableNumber(condition.value);
      return left !== null && right !== null && left > right;
    }
    case "gte": {
      const left = comparableNumber(actual);
      const right = comparableNumber(condition.value);
      return left !== null && right !== null && left >= right;
    }
    case "lt": {
      const left = comparableNumber(actual);
      const right = comparableNumber(condition.value);
      return left !== null && right !== null && left < right;
    }
    case "lte": {
      const left = comparableNumber(actual);
      const right = comparableNumber(condition.value);
      return left !== null && right !== null && left <= right;
    }
    case "in":
      return Array.isArray(condition.value)
        ? condition.value.includes(actual as never)
        : false;
    default:
      return false;
  }
}

export function evaluateConditions(
  root: Record<string, unknown>,
  conditions: AutomationCondition[],
): boolean {
  return conditions.every((condition) => evaluateCondition(root, condition));
}
