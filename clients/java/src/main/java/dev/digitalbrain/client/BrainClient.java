package dev.digitalbrain.client;

/**
 * Entry point for the Digital Brain API v1 Java client.
 *
 * <p>The client is deliberately thin: it speaks the same contract as the
 * TypeScript client over the same two transports and adds no Brain logic.
 */
public final class BrainClient {

    /** The API version this client speaks. */
    public static final String API_VERSION = "v1";

    /** The HTTP endpoint path of the Core HTTP transport. */
    public static final String API_PATH = BrainRequests.API_PATH;

    private BrainClient() {
    }

    /** An HTTP client for request/response access. */
    public static BrainHttpClient http(String baseUrl, String userId) {
        return new BrainHttpClient(baseUrl, userId);
    }

    /** A WebSocket client that also receives live Brain events. */
    public static BrainWebSocketClient websocket(String baseUrl, String userId) {
        return new BrainWebSocketClient(baseUrl, userId);
    }

    /** The method names this build knows, mirroring the canonical registry. */
    public static java.util.List<String> knownMethods() {
        return BrainRequests.knownMethods();
    }
}
