/**
 * Digital Brain API v1 — thin, framework-free TypeScript client.
 *
 * Public surface for both Product clients (PC and mobile): the wire contract,
 * the two transport clients and the error taxonomy. Nothing here renders UI,
 * captures audio, holds an auth session or executes a proposed action.
 */

export type {
  ApiError,
  ApiErrorCode,
  ApiMethod,
  ApiRequest,
  ApiResponse,
  ApiVersion,
  AssistanceProfileResult,
  AnalyzeDeveloperParams,
  AnalyzeDeveloperResult,
  BrainDecision,
  BrainEvent,
  BrainEventType,
  BuildContextParams,
  BugFindingWire,
  ContextResultWire,
  DeveloperFileWire,
  DeveloperPreferencesResult,
  DeveloperSnapshotWire,
  DescribeParams,
  DescribeResult,
  EmptyParams,
  EventEnvelope,
  Feedback,
  FeedbackHistoryItemWire,
  FeedbackHistoryParams,
  FeedbackHistoryResult,
  FeedbackKind,
  FeedbackResultWire,
  FeedbackSourceName,
  FeedbackTarget,
  GitSnapshotWire,
  HealthPayload,
  IngestParams,
  IngestionResultWire,
  IntentWire,
  JsonObject,
  LearningStatusResult,
  MethodParams,
  MethodResult,
  MethodSpec,
  NormalizedSourceEvent,
  NudgeWire,
  PeopleSummaryResult,
  PeopleTimelineEntryWire,
  PeopleTimelineParams,
  PeopleTimelineResult,
  PeopleTimelineSourceWire,
  PersonFactDurability,
  PersonResolutionResult,
  PersonRowWire,
  PingParams,
  PingResult,
  PlanWire,
  PreferenceEvidenceWire,
  PreferenceWire,
  PreferencesResult,
  ReasonParams,
  ReasoningWire,
  RecordFeedbackParams,
  RecordPreferenceParams,
  ResolvePersonParams,
  ResponseEnvelope,
  ReviewFindingWire,
  SignalWire,
  Source,
  StreamFrame,
  Subject,
  TestOutcomeWire,
  TestResultSnapshotWire,
  TopicAffinityWire,
  UnderstandParams,
  UnderstandResultWire,
  UserParams,
} from "./contract.ts";

export {
  API_ERROR_CODES,
  API_METHODS,
  API_VERSION,
  BRAIN_EVENT_TYPES,
  KNOWN_API_ERROR_CODES,
  apiMethodSpecs,
  isApiMethod,
  methodHasUserIdParam,
} from "./contract.ts";

export {
  BrainApiError,
  BrainClientError,
  BrainContractError,
  BrainTransportError,
  isApiErrorCode,
  isBrainApiError,
  isBrainClientError,
} from "./errors.ts";

export {
  DEFAULT_DEDUPE_CAPACITY,
  DEFAULT_REQUEST_TIMEOUT_MS,
  EventDispatcher,
  RequestBuilder,
  assertValidUserId,
  buildUserIdQuery,
  correlationIdOf,
  isEventEnvelope,
  isResponseEnvelope,
  joinUrl,
  parseStreamFrame,
  validateResponseEnvelope,
} from "./common.ts";

export type {
  EventDispatcherStats,
  EventHandler,
  RequestOptions,
} from "./common.ts";

export { HttpBrainClient } from "./http.ts";
export type { FetchLike, HttpBrainClientOptions } from "./http.ts";

export { WebSocketBrainClient, buildSocketUrl } from "./websocket.ts";
export type {
  WebSocketBrainClientOptions,
  WebSocketClientStats,
  WebSocketFactory,
  WebSocketLike,
  WebSocketReadyState,
} from "./websocket.ts";
