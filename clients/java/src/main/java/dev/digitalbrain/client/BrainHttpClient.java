package dev.digitalbrain.client;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.List;
import java.util.Map;

/**
 * HTTP transport client: one {@code ApiRequest} per call.
 *
 * <p>Uses only {@code java.net.http} from the JDK. The bundled Core HTTP
 * transport wires a null event sink, so this client is request/response only;
 * use {@link BrainWebSocketClient} for live events.
 */
public final class BrainHttpClient {

    private final URI baseUri;
    private final HttpClient http;
    private final Duration requestTimeout;
    private final BrainRequests requests;

    public BrainHttpClient(String baseUrl, String userId) {
        this(baseUrl, userId, Duration.ofSeconds(30));
    }

    public BrainHttpClient(String baseUrl, String userId, Duration requestTimeout) {
        if (baseUrl == null || baseUrl.trim().isEmpty()) {
            throw new IllegalArgumentException("baseUrl is required");
        }
        String normalized = baseUrl.endsWith("/")
                ? baseUrl.substring(0, baseUrl.length() - 1)
                : baseUrl;
        this.baseUri = URI.create(normalized);
        this.http = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(10))
                .version(HttpClient.Version.HTTP_1_1)
                .build();
        this.requestTimeout = requestTimeout == null ? Duration.ofSeconds(30) : requestTimeout;
        this.requests = new BrainRequests(userId, "brain", 1024);
    }

    /** The static liveness payload; contains no user data. */
    public Map<String, Object> health() {
        HttpResponse<String> response = send(
                HttpRequest.newBuilder(this.baseUri.resolve("/health")).GET());
        return Json.parseObject(response.body());
    }

    /**
     * Sends one request and returns the typed result.
     *
     * @throws BrainApiException when the Brain answered {@code ok=false}
     */
    public Object call(String method, Map<String, Object> params) {
        return requests.resultOf(request(method, params), method, null);
    }

    /** Sends one request and returns the full {@code ApiResponse} as a map. */
    public Map<String, Object> request(String method, Map<String, Object> params) {
        String id = requests.nextId();
        String body = Json.write(requests.request(method, params, id));
        HttpResponse<String> response = send(
                HttpRequest.newBuilder(this.baseUri.resolve(BrainRequests.API_PATH))
                        .header("Content-Type", "application/json")
                        .header("Accept", "application/json")
                        .timeout(this.requestTimeout)
                        .POST(HttpRequest.BodyPublishers.ofString(body))
                        .build());
        Map<String, Object> envelope = Json.parseObject(response.body());
        String returnedId = Json.optString(envelope, "id");
        if (returnedId != null && !returnedId.equals(id)) {
            throw new Json.JsonException("response id does not match the request");
        }
        return envelope;
    }

    /** The method names this build knows, mirroring the canonical registry. */
    public static List<String> knownMethods() {
        return BrainRequests.knownMethods();
    }

    private HttpResponse<String> send(HttpRequest request) {
        try {
            return this.http.send(request, HttpResponse.BodyHandlers.ofString());
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            throw new Json.JsonException("request interrupted");
        } catch (Exception exception) {
            throw new Json.JsonException("request failed: " + exception.getMessage());
        }
    }
}
