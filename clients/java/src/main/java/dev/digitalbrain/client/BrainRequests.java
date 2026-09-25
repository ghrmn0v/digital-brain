package dev.digitalbrain.client;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Shared request/response plumbing for the Java client.
 *
 * <p>Holds the parts that must behave identically for both transports: request
 * id minting, the {@code ApiRequest} envelope, the {@code ApiResponse}
 * invariants and the consumer-side event rules (deduplicate by
 * {@code BrainEvent.id}, filter by {@code user_id}, keep arrival order, group by
 * {@code payload.correlation_id}).
 */
public final class BrainRequests {

    public static final String API_VERSION = "v1";
    public static final String API_PATH = "/v1/brain";

    private final String userId;
    private final String idPrefix;
    private final AtomicLong counter = new AtomicLong();
    private final List<String> seenEventIds = new ArrayList<>();
    private final int dedupeCapacity;

    public BrainRequests(String userId, String idPrefix, int dedupeCapacity) {
        this.userId = userId;
        this.idPrefix = idPrefix == null || idPrefix.isEmpty() ? "brain" : idPrefix;
        this.dedupeCapacity = dedupeCapacity <= 0 ? 1024 : dedupeCapacity;
    }

    public String userId() {
        return this.userId;
    }

    /** A request id unique within this client instance. */
    public String nextId() {
        return this.idPrefix + "-" + this.counter.incrementAndGet();
    }

    /**
     * Builds one {@code ApiRequest}. {@code userId} is injected into params
     * that carry ownership, unless the caller already supplied the same value.
     */
    public Map<String, Object> request(String method, Map<String, Object> params, String id) {
        Map<String, Object> envelope = new LinkedHashMap<>();
        envelope.put("id", id);
        envelope.put("method", method);
        envelope.put("version", API_VERSION);
        Map<String, Object> body = params == null ? new LinkedHashMap<>() : new LinkedHashMap<>(params);
        if (this.userId != null && !this.userId.isEmpty() && !body.containsKey("user_id")) {
            body.put("user_id", this.userId);
        }
        envelope.put("params", body);
        return envelope;
    }

    /**
     * Validates an {@code ApiResponse} and returns its {@code result}.
     *
     * @throws BrainApiException when the Brain answered {@code ok=false}
     * @throws Json.JsonException when the body is not a Brain response
     */
    public Object resultOf(Map<String, Object> response, String method, String expectedId) {
        String id = Json.optString(response, "id");
        if (id == null || id.isEmpty()) {
            throw new Json.JsonException("response is missing a string id");
        }
        if (expectedId != null && !expectedId.equals(id)) {
            throw new Json.JsonException("response id does not match the request");
        }
        Object ok = response.get("ok");
        if (!(ok instanceof Boolean)) {
            throw new Json.JsonException("response is missing a boolean ok");
        }
        if (Boolean.TRUE.equals(ok)) {
            return response.get("result");
        }
        Map<String, Object> error = Json.optObject(response, "error");
        String code = error == null ? null : Json.optString(error, "code");
        String message = error == null ? "request failed" : Json.optString(error, "message");
        throw new BrainApiException(code, message, method, id);
    }

    // -- event rules -----------------------------------------------------------

    /** True when this event was already delivered inside the dedupe window. */
    public boolean alreadySeen(String eventId) {
        if (eventId == null) {
            return false;
        }
        if (seenEventIds.contains(eventId)) {
            return true;
        }
        seenEventIds.add(eventId);
        if (seenEventIds.size() > this.dedupeCapacity) {
            seenEventIds.remove(0);
        }
        return false;
    }

    /** True when the event belongs to the connection identity. */
    public boolean belongsToUser(Map<String, Object> event) {
        String owner = Json.optString(event, "user_id");
        return this.userId != null && this.userId.equals(owner);
    }

    /** The correlation id of an event, or {@code null} when it has none. */
    public static String correlationId(Map<String, Object> event) {
        Map<String, Object> payload = Json.optObject(event, "payload");
        if (payload == null) {
            return null;
        }
        String correlationId = Json.optString(payload, "correlation_id");
        return correlationId == null || correlationId.isEmpty() ? null : correlationId;
    }

    /** The method names this build of the client knows, for drift checks. */
    public static List<String> knownMethods() {
        List<String> methods = new ArrayList<>();
        Collections.addAll(
                methods,
                "ping",
                "describe",
                "ingest",
                "record_feedback",
                "record_preference",
                "understand",
                "build_context",
                "analyze_developer",
                "reason",
                "preferences",
                "developer_preferences",
                "people_summary",
                "people_timeline",
                "learning_status",
                "feedback_history",
                "personalization_profile",
                "resolve_person",
                // Appended, never inserted: the order mirrors the canonical
                // registry so a caller comparing tables sees the same sequence.
                "search",
                "chat");
        return methods;
    }
}
