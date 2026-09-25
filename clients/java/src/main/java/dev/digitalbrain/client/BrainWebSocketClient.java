package dev.digitalbrain.client;

import java.net.URI;
import java.net.URLEncoder;
import java.net.http.WebSocket;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;

/**
 * WebSocket transport client: one bidirectional connection to
 * {@code {wsBase}/v1/brain?user_id=...} carrying {@code kind}-tagged response
 * and event frames.
 *
 * <p>Implements the consumer rules the Core documents: one outstanding response
 * per connection, responses correlated by request id, events delivered
 * at-most-once and deduplicated by {@code BrainEvent.id}, filtered by the
 * connection identity, in arrival order. No retry, no replay, no persistence.
 *
 * <p>Only {@code java.net.http.WebSocket} is used — no third-party dependency.
 */
public final class BrainWebSocketClient {

    /** Receives one decoded {@code BrainEvent}. */
    public interface EventListener {
        void onEvent(Map<String, Object> event);
    }

    private static final Duration DEFAULT_RESPONSE_TIMEOUT = Duration.ofSeconds(30);

    private final URI uri;
    private final WebSocket.Builder builder;
    private final BrainRequests requests;
    private final Map<String, CompletableFuture<Object>> pending = new ConcurrentHashMap<>();
    private final Duration responseTimeout;
    private WebSocket socket;
    private volatile EventListener listener;

    public BrainWebSocketClient(String baseUrl, String userId) {
        this(baseUrl, userId, DEFAULT_RESPONSE_TIMEOUT);
    }

    public BrainWebSocketClient(String baseUrl, String userId, Duration responseTimeout) {
        if (baseUrl == null || baseUrl.trim().isEmpty()) {
            throw new IllegalArgumentException("url is required");
        }
        if (userId == null || userId.trim().isEmpty()) {
            throw new IllegalArgumentException("userId is required");
        }
        String normalized = baseUrl.endsWith("/")
                ? baseUrl.substring(0, baseUrl.length() - 1)
                : baseUrl;
        String wsBase = normalized
                .replaceFirst("^http://", "ws://")
                .replaceFirst("^https://", "wss://");
        String target = wsBase.contains(BrainRequests.API_PATH)
                ? wsBase + (wsBase.contains("?") ? "&" : "?") + "user_id=" + encode(userId)
                : wsBase + BrainRequests.API_PATH + "?user_id=" + encode(userId);
        this.uri = URI.create(target);
        this.builder = WebSocket.newBuilder(this.uri);
        this.requests = new BrainRequests(userId, "brain", 1024);
        this.responseTimeout = responseTimeout == null ? DEFAULT_RESPONSE_TIMEOUT : responseTimeout;
    }

    /** The connection identity, also used to filter events. */
    public String userId() {
        return this.requests.userId();
    }

    /** The connection URL, useful for diagnostics. */
    public String url() {
        return this.uri.toString();
    }

    /** Subscribes to Brain events for the connection identity. */
    public void onEvent(EventListener eventListener) {
        this.listener = eventListener;
    }

    /** Opens the connection and waits for it to be established. */
    public CompletableFuture<Void> connect() {
        WebSocket existing = this.socket;
        if (existing != null) {
            return CompletableFuture.completedFuture(null);
        }
        CompletableFuture<Void> opened = new CompletableFuture<>();
        this.builder.buildAsync(this.uri, new Listener(opened)).whenComplete((webSocket, error) -> {
            if (error != null) {
                opened.completeExceptionally(error);
                return;
            }
            this.socket = webSocket;
            opened.complete(null);
        });
        return opened;
    }

    /**
     * Sends one request and waits for its response frame.
     *
     * @throws BrainApiException when the Brain answered {@code ok=false}
     * @throws IllegalStateException when the connection is not open
     */
    public Object call(String method, Map<String, Object> params) {
        Pending pendingRequest = this.enqueue(method, params);
        try {
            return pendingRequest.result.get(this.responseTimeout.toMillis(), TimeUnit.MILLISECONDS);
        } catch (TimeoutException exception) {
            this.pending.remove(pendingRequest.id);
            throw new Json.JsonException("request timed out: " + method);
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            throw new Json.JsonException("request interrupted: " + method);
        } catch (ExecutionException exception) {
            Throwable cause = exception.getCause();
            if (cause instanceof RuntimeException) {
                throw (RuntimeException) cause;
            }
            throw new Json.JsonException("request failed: " + cause);
        } finally {
            this.pending.remove(pendingRequest.id);
        }
    }

    /** Sends one request without waiting and returns its request id. */
    public String send(String method, Map<String, Object> params) {
        return this.enqueue(method, params).id;
    }

    /**
     * Registers the pending response before writing, so a fast response can
     * never arrive before its waiter exists.
     */
    private Pending enqueue(String method, Map<String, Object> params) {
        WebSocket current = this.socket;
        if (current == null) {
            throw new IllegalStateException("not connected; call connect() first");
        }
        String id = this.requests.nextId();
        CompletableFuture<Object> result = new CompletableFuture<>();
        this.pending.put(id, result);
        current.sendText(Json.write(this.requests.request(method, params, id)), true);
        return new Pending(id, result);
    }

    /** One in-flight request: its id and the future its response completes. */
    private static final class Pending {
        private final String id;
        private final CompletableFuture<Object> result;

        Pending(String id, CompletableFuture<Object> result) {
            this.id = id;
            this.result = result;
        }
    }

    /** The correlation id of an event, for grouping related events. */
    public static String correlationId(Map<String, Object> event) {
        return BrainRequests.correlationId(event);
    }

    /** Closes the connection with a normal status. */
    public void close() {
        WebSocket current = this.socket;
        this.socket = null;
        if (current != null) {
            current.sendClose(WebSocket.NORMAL_CLOSURE, "client closed");
        }
        for (CompletableFuture<Object> waiter : this.pending.values()) {
            waiter.completeExceptionally(new IllegalStateException("client closed"));
        }
        this.pending.clear();
    }

    private void handle(String message) {
        Map<String, Object> frame;
        try {
            frame = Json.parseObject(message);
        } catch (RuntimeException exception) {
            return;
        }
        String kind = Json.optString(frame, "kind");
        Map<String, Object> payload = Json.optObject(frame, "payload");
        if (kind == null || payload == null) {
            return;
        }
        if ("event".equals(kind)) {
            deliverEvent(payload);
            return;
        }
        if (!"response".equals(kind)) {
            return;
        }
        String id = Json.optString(payload, "id");
        if (id == null) {
            return;
        }
        CompletableFuture<Object> waiter = this.pending.remove(id);
        if (waiter == null) {
            return;
        }
        try {
            waiter.complete(this.requests.resultOf(payload, Json.optString(payload, "method"), id));
        } catch (RuntimeException exception) {
            waiter.completeExceptionally(exception);
        }
    }

    private void deliverEvent(Map<String, Object> event) {
        if (this.requests.alreadySeen(Json.optString(event, "id"))) {
            return;
        }
        if (!this.requests.belongsToUser(event)) {
            return;
        }
        EventListener current = this.listener;
        if (current != null) {
            current.onEvent(event);
        }
    }

    private static String encode(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8).replace("+", "%20");
    }

    /** Adapts the push-based listener to the blocking request API. */
    private final class Listener implements WebSocket.Listener {

        private final CompletableFuture<Void> opened;
        private final StringBuilder partial = new StringBuilder();

        Listener(CompletableFuture<Void> opened) {
            this.opened = opened;
        }

        @Override
        public void onOpen(WebSocket webSocket) {
            webSocket.request(1);
        }

        @Override
        public java.util.concurrent.CompletionStage<?> onText(
                WebSocket webSocket, CharSequence data, boolean last) {
            this.partial.append(data);
            if (last) {
                String message = this.partial.toString();
                this.partial.setLength(0);
                BrainWebSocketClient.this.handle(message);
            }
            webSocket.request(1);
            return null;
        }

        @Override
        public java.util.concurrent.CompletionStage<?> onClose(
                WebSocket webSocket, int statusCode, String reason) {
            BrainWebSocketClient.this.socket = null;
            return null;
        }

        @Override
        public void onError(WebSocket webSocket, Throwable error) {
            BrainWebSocketClient.this.socket = null;
            this.opened.completeExceptionally(error);
        }
    }
}
