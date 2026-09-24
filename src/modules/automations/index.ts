export {
  AUTOMATION_RUN_STATUSES,
  AUTOMATION_TRIGGER_KINDS,
  automationCreateSchema,
  automationListQuerySchema,
  automationUpdateSchema,
  type AutomationCreateInput,
  type AutomationDto,
  type AutomationListQuery,
  type AutomationRunStatus,
  type AutomationTriggerKind,
  type AutomationUpdateInput,
} from "./contracts";
export {
  evaluateCondition,
  evaluateConditions,
  getValueAtPath,
  type AutomationCondition,
  type ConditionOperator,
} from "./condition-evaluator";
export { automationService } from "./service";
