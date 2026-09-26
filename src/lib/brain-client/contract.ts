/**
 * Digital Brain API v1 — TypeScript wire contract.
 *
 * Hand-maintained mirror of `contracts/schemas/brain-api.v1.json` (Slice 5A).
 * The runtime `API_METHODS` table and `API_ERROR_CODES` list are verified
 * against that artifact by `test/contract.test.ts`, so method order and
 * definition names cannot drift silently.
 *
 * Field shapes follow the generated JSON Schema. Where the Core contract
 * deliberately keeps a payload open (for example `BrainEvent.payload` or the
 * `understand`/`reason` analyses), the value is typed as `unknown` or an open
 * record instead of being guessed into a closed shape.
 */

export const API_VERSION = "v1" as const;

export type ApiVersion = typeof API_VERSION;

export const API_ERROR_CODES = [
  "bad_request",
  "unknown_method",
  "version_unsupported",
  "validation_error",
  "not_configured",
  "internal_error",
] as const;

export type ApiErrorCode = (typeof API_ERROR_CODES)[number];

export type JsonObject = { readonly [key: string]: unknown };

/** Forward-compatible reading: a newer Core may add an error code. */
export const KNOWN_API_ERROR_CODES: ReadonlySet<string> = new Set(API_ERROR_CODES);

export interface Source {
  readonly provider: string;
  readonly component?: string | null;
  readonly version?: string | null;
}

export interface ApiError {
  readonly code: string;
  readonly message: string;
  readonly source?: string | null;
  // `| undefined` is explicit so the type stays assignable under
  // `exactOptionalPropertyTypes`, which consumers of this client enable.
  readonly details?: JsonObject | undefined;
}

export interface ApiRequest<P = JsonObject> {
  readonly id: string;
  readonly method: string;
  readonly version?: ApiVersion;
  readonly params?: P;
  readonly source?: Source | null;
}

export interface ApiResponse<T = JsonObject> {
  readonly id: string;
  readonly ok: boolean;
  readonly method?: string | null;
  readonly version?: ApiVersion;
  readonly result?: T | null;
  readonly error?: ApiError | null;
}

export const BRAIN_EVENT_TYPES = [
  "memory.created",
  "memory.updated",
  "person.created",
  "person.updated",
  "preference.updated",
  "action.proposed",
  "decision.created",
  "learning.signal.detected",
  "developer.bug_detected",
  "developer.fix_proposed",
  "developer.test_result",
  "developer.review_finding",
  "developer.deploy_proposed",
] as const;

export type BrainEventType = (typeof BRAIN_EVENT_TYPES)[number];

export interface BrainEvent {
  readonly id: string;
  readonly type: BrainEventType | string;
  readonly timestamp: string;
  readonly user_id: string;
  readonly source: Source;
  readonly payload?: JsonObject;
  readonly related_ids?: readonly string[];
  readonly version?: string;
}

export interface ResponseEnvelope {
  readonly kind: "response";
  readonly payload: ApiResponse;
}

export interface EventEnvelope {
  readonly kind: "event";
  readonly payload: BrainEvent;
}

export type StreamFrame = ResponseEnvelope | EventEnvelope;

export interface HealthPayload {
  readonly status: string;
  readonly service: string;
  readonly api_version: string;
}

export type PersonFactDurability = "durable" | "temporary" | "unspecified";

export interface Subject {
  readonly person_id?: string | null;
  /**
   * The connector's own name for the person. When present without
   * `person_id`, Core resolves the identity deterministically instead of
   * asking the connector to invent an id.
   */
  readonly person_name?: string | null;
  readonly role?: string | null;
}

export interface NormalizedSourceEvent {
  readonly id: string;
  readonly type: string;
  readonly timestamp: string;
  readonly user_id: string;
  readonly source: Source;
  readonly occurred_at: string;
  readonly subject?: Subject | null;
  readonly payload?: JsonObject;
  readonly correlation_id?: string | null;
  readonly idempotency_key?: string | null;
  readonly version?: string;
}

export type FeedbackKind = "explicit" | "implicit" | "outcome" | "reward";

export type FeedbackSourceName = "user" | "product" | "fly" | "system";

export interface FeedbackTarget {
  readonly memory_id?: string | null;
  readonly event_id?: string | null;
  readonly decision_id?: string | null;
  readonly action_id?: string | null;
}

export interface Feedback {
  readonly feedback_id: string;
  readonly user_id: string;
  readonly source: FeedbackSourceName;
  readonly kind: FeedbackKind;
  readonly target: FeedbackTarget;
  readonly created_at: string;
  readonly note?: string | null;
  readonly label?: string | null;
  readonly value?: number | null;
  readonly metadata?: JsonObject;
  readonly correlation_id?: string | null;
  readonly version?: string;
}

export interface DeveloperFileWire {
  readonly path: string;
  readonly content?: string;
  readonly language?: string | null;
}

export interface GitSnapshotWire {
  readonly branch?: string | null;
  readonly dirty?: boolean | null;
  readonly recent_commits?: readonly string[];
  readonly remote?: string | null;
}

export interface TestResultSnapshotWire {
  readonly status: string;
  readonly name?: string | null;
  readonly file?: string | null;
  readonly message?: string | null;
}

export interface DeveloperSnapshotWire {
  readonly user_id: string;
  readonly repository: string;
  readonly root?: string | null;
  readonly current_file?: string | null;
  readonly current_line?: number | null;
  readonly changed_files?: readonly string[];
  readonly files?: readonly DeveloperFileWire[];
  readonly git_context?: GitSnapshotWire | null;
  readonly test_results?: readonly TestResultSnapshotWire[];
  readonly user_context?: JsonObject;
  readonly version?: string;
}

export interface PreferenceWire {
  readonly memory_id: string;
  readonly name: string;
  readonly value: string;
  readonly confidence: number;
  readonly importance: number;
  readonly domain?: string | null;
}

export interface SignalWire {
  readonly kind: string;
  readonly source: string;
  readonly strength: number;
  readonly topic?: string | null;
  readonly preference_domain?: string | null;
  readonly preference_name?: string | null;
  readonly correlation_id?: string | null;
}

export interface TopicAffinityWire {
  readonly topic: string;
  readonly positive: number;
  readonly negative: number;
  readonly ignored: number;
  readonly direction?: string;
  readonly positive_rate?: number | null;
}

export interface PreferenceEvidenceWire {
  readonly key: string;
  readonly name: string;
  readonly positive: number;
  readonly negative: number;
  readonly weight: number;
  readonly domain?: string | null;
  readonly positive_rate?: number | null;
}

export interface NudgeWire {
  readonly topic: string;
  readonly direction: string;
  readonly strength: number;
  readonly suggestion: string;
}

export interface FeedbackHistoryItemWire {
  readonly stored_at: string;
  readonly memory_id: string;
  readonly kind: string;
  readonly source: string;
  readonly strength: number;
  readonly correlation_id?: string | null;
  readonly note?: string | null;
  readonly topic?: string | null;
}

export interface PersonRowWire {
  readonly person_id: string;
  readonly mention_count: number;
  readonly name?: string | null;
}

export interface PersonTimelineSourceWire {
  readonly provider: string;
  readonly component?: string | null;
  readonly version?: string | null;
  readonly source_event_id?: string | null;
  readonly source_event_id_truncated?: boolean;
  readonly correlation_id?: string | null;
  readonly correlation_id_truncated?: boolean;
  readonly related_event_ids?: readonly string[];
  readonly evidence?: JsonObject;
}

export interface PersonTimelineEntryWire {
  readonly person_id: string;
  readonly memory_id: string;
  readonly memory_type: string;
  readonly status: string;
  readonly statement: string;
  readonly occurred_at: string;
  readonly created_at: string;
  readonly durability: PersonFactDurability | string;
  readonly confidence: number;
  readonly importance: number;
  readonly provenance: PersonTimelineSourceWire;
  readonly statement_truncated?: boolean;
  readonly valid_until?: string | null;
}

export interface IntentWire {
  readonly intent_kind: string;
  readonly confidence: number;
  readonly keywords?: readonly string[];
  readonly query?: string;
  readonly repository?: string | null;
  readonly target_file?: string | null;
  readonly target_line?: number | null;
  readonly fallback_used?: boolean;
}

export interface TestOutcomeWire {
  readonly provided: boolean;
  readonly passed: number;
  readonly failed: number;
  readonly skipped: number;
  readonly errors: number;
  readonly summary: string;
  readonly reason?: string | null;
}

export interface BugFindingWire {
  readonly finding_id: string;
  readonly repository: string;
  readonly file: string;
  readonly line: number;
  readonly title: string;
  readonly message: string;
  readonly severity: string;
  readonly confidence: number;
  readonly check: string;
  readonly column?: number | null;
  readonly suggested_fix?: string | null;
}

export interface ReviewFindingWire {
  readonly finding_id: string;
  readonly repository: string;
  readonly file: string;
  readonly line: number;
  readonly category: string;
  readonly severity: string;
  readonly explanation: string;
  readonly confidence: number;
  readonly suggestion?: string | null;
}

export interface BrainDecision {
  readonly decision_id?: string;
  readonly rationale?: string;
  readonly [key: string]: unknown;
}

export interface ReasoningWire {
  readonly user_id: string;
  readonly repository: string;
  readonly created_at: string;
  readonly intent: IntentWire;
  readonly tests: TestOutcomeWire;
  readonly files_scanned: number;
  readonly total_changed: number;
  readonly bugs?: readonly BugFindingWire[];
  readonly review_findings?: readonly ReviewFindingWire[];
  readonly context_used?: boolean;
  readonly learning_used?: boolean;
}

export interface PlanWire {
  readonly correlation_id: string;
  readonly decision: BrainDecision;
  readonly proposed_actions?: readonly JsonObject[];
}

export type EmptyParams = Readonly<Record<string, never>>;

export type PingParams = EmptyParams;
export type DescribeParams = EmptyParams;

export interface IngestParams {
  readonly event: NormalizedSourceEvent;
  readonly correlation_id?: string | null;
}

export interface RecordFeedbackParams {
  readonly feedback: Feedback;
  readonly correlation_id?: string | null;
}

export interface RecordPreferenceParams {
  readonly user_id: string;
  readonly name: string;
  readonly value: string;
  readonly domain?: string | null;
  readonly confidence?: number | null;
  readonly importance?: number | null;
  readonly metadata?: JsonObject;
  readonly correlation_id?: string | null;
  readonly source?: Source | null;
}

export interface UnderstandParams {
  readonly corpus: string;
  readonly corpus_id?: string | null;
  readonly user_id?: string | null;
}

export interface BuildContextParams {
  readonly context: DeveloperSnapshotWire;
  readonly task?: string | null;
}

export interface ReasonParams {
  readonly context: DeveloperSnapshotWire;
  readonly task?: string | null;
}

export interface AnalyzeDeveloperParams {
  readonly context: DeveloperSnapshotWire;
  readonly task?: string | null;
  readonly ask_deploy?: boolean;
  readonly correlation_id?: string | null;
}

export interface UserParams {
  readonly user_id: string;
}

export interface PeopleTimelineParams {
  readonly user_id: string;
  readonly person_id: string;
  readonly limit?: number | null;
}

export interface FeedbackHistoryParams {
  readonly user_id: string;
  readonly limit?: number | null;
}

export interface ResolvePersonParams {
  readonly user_id: string;
  readonly name: string;
  readonly aliases?: readonly string[];
  readonly correlation_id?: string | null;
}

export interface IngestionResultWire {
  readonly outcome: string;
  readonly event_id: string;
  readonly user_id: string;
  readonly events_emitted: number;
  readonly correlation_id?: string | null;
  readonly duplicate_of_event_id?: string | null;
  readonly memory_ids?: readonly string[];
  readonly reason?: string | null;
}

export interface FeedbackResultWire {
  readonly user_id: string;
  readonly stored_at: string;
  readonly memory_id: string;
  readonly signal: SignalWire;
}

export interface UnderstandResultWire {
  readonly intent: string;
  readonly confidence: number;
  readonly summary: string;
  readonly corpus_id?: string | null;
  readonly entities?: readonly string[];
  readonly fallback_used?: boolean;
  readonly provider?: string;
  readonly relevant_code_concepts?: readonly string[];
  readonly salience?: number;
  readonly topics?: readonly string[];
  readonly user_id?: string | null;
  readonly version?: string;
}

export interface ContextResultWire {
  readonly context_id: string;
  readonly user_id: string;
  readonly status: string;
  readonly relevant_memory_count: number;
  readonly previous_bug_finding_count: number;
  readonly previous_decision_count: number;
  readonly developer_preference_count: number;
  readonly relevant_people_count: number;
  readonly current_file?: string | null;
  readonly current_task?: string | null;
  readonly fallback_used?: boolean;
  readonly repository?: string | null;
}

export interface AnalyzeDeveloperResult {
  readonly user_id: string;
  readonly correlation_id: string;
  readonly reasoning: ReasoningWire;
  readonly plan: PlanWire;
  readonly events?: readonly BrainEvent[];
}

export interface PreferencesResult {
  readonly user_id: string;
  readonly preferences?: readonly PreferenceWire[];
  readonly domains?: readonly string[];
}

export interface DeveloperPreferencesResult {
  readonly user_id: string;
  readonly languages?: readonly PreferenceWire[];
  readonly testing?: readonly PreferenceWire[];
  readonly coding_style?: readonly PreferenceWire[];
  readonly commit_style?: readonly PreferenceWire[];
  readonly explanation_detail?: readonly PreferenceWire[];
  readonly deployment?: readonly PreferenceWire[];
}

export interface PeopleSummaryResult {
  readonly user_id: string;
  readonly people?: readonly PersonRowWire[];
}

export interface PeopleTimelineResult {
  readonly user_id: string;
  readonly person_id: string;
  readonly total_entries: number;
  readonly entries?: readonly PersonTimelineEntryWire[];
  readonly person_known?: boolean;
  readonly scan_truncated?: boolean;
  readonly truncated?: boolean;
}

export interface LearningStatusResult {
  readonly user_id: string;
  readonly preference_evidence?: readonly PreferenceEvidenceWire[];
  readonly signal_counts?: Readonly<Record<string, number>>;
  readonly topics?: readonly TopicAffinityWire[];
}

export interface FeedbackHistoryResult {
  readonly user_id: string;
  readonly items?: readonly FeedbackHistoryItemWire[];
}

/**
 * Outcome of resolving one person name. `person_id` is present exactly when the
 * name is not ambiguous; an ambiguous result lists the competing ids in
 * `candidates` and never merges them.
 */
export interface PersonResolutionResult {
  readonly user_id: string;
  readonly name: string;
  readonly person_id?: string | null;
  readonly aliases?: readonly string[];
  readonly created?: boolean;
  readonly ambiguous?: boolean;
  readonly candidates?: readonly string[];
  readonly memory_id?: string | null;
}

// -- retrieval (search) and conversation (chat) ---------------------------------

/** The Brain's coarse memory taxonomy; additive, and an unknown value is an error. */
export type MemoryTypeWire =
  | "fact"
  | "episode"
  | "interaction"
  | "relationship"
  | "preference"
  | "event"
  | "observation";

export interface SearchParams {
  readonly user_id: string;
  readonly text?: string;
  readonly keywords?: readonly string[];
  readonly memory_type?: MemoryTypeWire | null;
  readonly person_id?: string | null;
  readonly importance_min?: number | null;
  readonly limit?: number;
  readonly correlation_id?: string | null;
}

export interface MemoryHitWire {
  readonly memory_id: string;
  readonly type: string;
  readonly content: string;
  readonly content_truncated?: boolean;
  readonly score: number;
  readonly matched_fields?: readonly string[];
  readonly ranking_reason?: string;
  readonly confidence: number;
  readonly importance: number;
  readonly status: string;
  readonly source_provider?: string | null;
  readonly source_component?: string | null;
  readonly created_at: string;
  readonly updated_at: string;
  readonly person_ids?: readonly string[];
  readonly related_event_ids?: readonly string[];
  readonly correlation_id?: string | null;
}

export interface SearchResultWire {
  readonly user_id: string;
  readonly query: string;
  readonly items: readonly MemoryHitWire[];
  readonly total_returned: number;
  readonly truncated?: boolean;
  readonly correlation_id?: string | null;
}

export interface ChatParams {
  readonly user_id: string;
  readonly message: string;
  readonly session_id?: string | null;
  readonly limit?: number;
  readonly target_event_id?: string | null;
  readonly record_learning?: boolean;
  readonly correlation_id?: string | null;
}

export interface ChatGroundingWire {
  readonly memory_id: string;
  readonly type: string;
  readonly score: number;
  readonly content: string;
  readonly content_truncated?: boolean;
}

export interface ChatResultWire {
  readonly user_id: string;
  readonly session_id?: string | null;
  readonly message: string;
  readonly answer: string;
  readonly confidence: number;
  readonly provider: string;
  readonly fallback_used?: boolean;
  readonly grounded_in?: readonly ChatGroundingWire[];
  readonly context_fact_count?: number;
  readonly missing_context?: readonly string[];
  readonly learning_recorded?: number;
  readonly correlation_id?: string | null;
}

export interface AssistanceProfileResult {
  readonly user_id: string;
  readonly feedback_count: number;
  readonly preference_count: number;
  readonly generated_at: string;
  readonly avoid_topics?: readonly TopicAffinityWire[];
  readonly explanation_detail?: PreferenceWire | null;
  readonly nudges?: readonly NudgeWire[];
  readonly source_memory_ids?: readonly string[];
  readonly top_affinities?: readonly TopicAffinityWire[];
}

export interface PingResult {
  readonly ok?: boolean;
  readonly service?: string;
  readonly api_version?: string;
}

export interface DescribeResult {
  readonly methods?: readonly string[];
  readonly schemas?: Readonly<Record<string, JsonObject>>;
  readonly version?: string;
}

export interface ApiMethodDescriptor {
  readonly method: string;
  readonly paramsDef: string;
  readonly resultDef: string;
  readonly hasUserIdParam: boolean;
}

/**
 * The v1 method registry in declared order. `paramsDef`/`resultDef` are the
 * `$defs` names from the canonical schema artifact; `hasUserIdParam` marks the
 * methods whose params carry a top-level `user_id`, which is what a client
 * injects from its configured identity.
 */
export const API_METHODS = [
  { method: "ping", paramsDef: "PingParams", resultDef: "PingResult", hasUserIdParam: false },
  { method: "describe", paramsDef: "DescribeParams", resultDef: "DescribeResult", hasUserIdParam: false },
  { method: "ingest", paramsDef: "IngestParams", resultDef: "IngestionResultWire", hasUserIdParam: false },
  { method: "record_feedback", paramsDef: "RecordFeedbackParams", resultDef: "FeedbackResultWire", hasUserIdParam: false },
  { method: "record_preference", paramsDef: "RecordPreferenceParams", resultDef: "PreferenceWire", hasUserIdParam: true },
  { method: "understand", paramsDef: "UnderstandParams", resultDef: "UnderstandResultWire", hasUserIdParam: false },
  { method: "build_context", paramsDef: "BuildContextParams", resultDef: "ContextResultWire", hasUserIdParam: false },
  { method: "analyze_developer", paramsDef: "AnalyzeDeveloperParams", resultDef: "AnalyzeDeveloperResult", hasUserIdParam: false },
  { method: "reason", paramsDef: "ReasonParams", resultDef: "ReasoningWire", hasUserIdParam: false },
  { method: "preferences", paramsDef: "UserParams", resultDef: "PreferencesResult", hasUserIdParam: true },
  { method: "developer_preferences", paramsDef: "UserParams", resultDef: "DeveloperPreferencesResult", hasUserIdParam: true },
  { method: "people_summary", paramsDef: "UserParams", resultDef: "PeopleSummaryResult", hasUserIdParam: true },
  { method: "people_timeline", paramsDef: "PeopleTimelineParams", resultDef: "PeopleTimelineResult", hasUserIdParam: true },
  { method: "learning_status", paramsDef: "UserParams", resultDef: "LearningStatusResult", hasUserIdParam: true },
  { method: "feedback_history", paramsDef: "FeedbackHistoryParams", resultDef: "FeedbackHistoryResult", hasUserIdParam: true },
  { method: "personalization_profile", paramsDef: "UserParams", resultDef: "AssistanceProfileResult", hasUserIdParam: true },
  { method: "resolve_person", paramsDef: "ResolvePersonParams", resultDef: "PersonResolutionWire", hasUserIdParam: true },
  { method: "search", paramsDef: "SearchParams", resultDef: "SearchResultWire", hasUserIdParam: true },
  { method: "chat", paramsDef: "ChatParams", resultDef: "ChatResultWire", hasUserIdParam: true },
] as const satisfies readonly ApiMethodDescriptor[];

export type ApiMethod = (typeof API_METHODS)[number]["method"];

export interface MethodParamsMap {
  ping: PingParams;
  describe: DescribeParams;
  ingest: IngestParams;
  record_feedback: RecordFeedbackParams;
  record_preference: RecordPreferenceParams;
  understand: UnderstandParams;
  build_context: BuildContextParams;
  analyze_developer: AnalyzeDeveloperParams;
  reason: ReasonParams;
  preferences: UserParams;
  developer_preferences: UserParams;
  people_summary: UserParams;
  people_timeline: PeopleTimelineParams;
  learning_status: UserParams;
  feedback_history: FeedbackHistoryParams;
  personalization_profile: UserParams;
  resolve_person: ResolvePersonParams;
  search: SearchParams;
  chat: ChatParams;
}

export interface MethodResultMap {
  ping: PingResult;
  describe: DescribeResult;
  ingest: IngestionResultWire;
  record_feedback: FeedbackResultWire;
  record_preference: PreferenceWire;
  understand: UnderstandResultWire;
  build_context: ContextResultWire;
  analyze_developer: AnalyzeDeveloperResult;
  reason: ReasoningWire;
  preferences: PreferencesResult;
  developer_preferences: DeveloperPreferencesResult;
  people_summary: PeopleSummaryResult;
  people_timeline: PeopleTimelineResult;
  learning_status: LearningStatusResult;
  feedback_history: FeedbackHistoryResult;
  personalization_profile: AssistanceProfileResult;
  resolve_person: PersonResolutionResult;
  search: SearchResultWire;
  chat: ChatResultWire;
}

export type MethodParams<M extends ApiMethod> = MethodParamsMap[M];

export type MethodResult<M extends ApiMethod> = MethodResultMap[M];

export interface MethodSpec {
  readonly method: string;
  readonly paramsDef: string;
  readonly resultDef: string;
}

export function apiMethodSpecs(): readonly MethodSpec[] {
  return API_METHODS.map((entry) => ({
    method: entry.method,
    paramsDef: entry.paramsDef,
    resultDef: entry.resultDef,
  }));
}

export function isApiMethod(value: string): value is ApiMethod {
  return API_METHODS.some((entry) => entry.method === value);
}

export function methodHasUserIdParam(method: string): boolean {
  const entry = API_METHODS.find((candidate) => candidate.method === method);
  return entry === undefined ? false : entry.hasUserIdParam;
}
