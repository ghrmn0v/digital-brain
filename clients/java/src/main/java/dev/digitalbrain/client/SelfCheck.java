package dev.digitalbrain.client;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Dependency-free self check.
 *
 * <p>Run the local checks (no server needed):
 *
 * <pre>{@code
 * java -cp target/classes dev.digitalbrain.client.SelfCheck
 * }</pre>
 *
 * <p>Run them plus a live round trip against a running Core:
 *
 * <pre>{@code
 * java -cp target/classes dev.digitalbrain.client.SelfCheck http://127.0.0.1:8765 usr_ali
 * }</pre>
 *
 * <p>Exit code {@code 0} means every check passed.
 */
public final class SelfCheck {

    private static int failures = 0;

    private SelfCheck() {
    }

    public static void main(String[] args) {
        jsonRoundTrip();
        escaping();
        eventRules();
        methodTable();

        if (args.length >= 2) {
            liveRoundTrip(args[0], args[1]);
        } else {
            System.out.println("no base url given; skipped the live round trip");
        }

        if (failures == 0) {
            System.out.println("self check passed");
        } else {
            System.out.println("self check FAILED: " + failures + " check(s)");
            System.exit(1);
        }
    }

    private static void jsonRoundTrip() {
        String text = "{\"id\":\"req-1\",\"ok\":true,\"result\":{\"entries\":[1,2.5,true,null],\"s\":\"x\"}}";
        Map<String, Object> parsed = Json.parseObject(text);
        check("json id", "req-1".equals(Json.optString(parsed, "id")));
        check("json ok", Boolean.TRUE.equals(parsed.get("ok")));
        Map<String, Object> result = Json.optObject(parsed, "result");
        check("json nested object", result != null);
        check("json array size", result != null && Json.optArray(result, "entries").size() == 4);
        check("json round trip", text.equals(Json.write(parsed)));

        expectParseFailure("json rejects trailing content", "{\"a\":1} garbage");
        expectObjectParseFailure("json rejects an unterminated string", "{\"a\":\"x");
        expectObjectParseFailure("json rejects a non-object read", "[1,2]");
    }

    private static void escaping() {
        Map<String, Object> object = Json.object();
        object.put("text", "line\n\"quoted\"\tend");
        String written = Json.write(object);
        Map<String, Object> parsed = Json.parseObject(written);
        check(
                "escaping round trip",
                "line\n\"quoted\"\tend".equals(Json.optString(parsed, "text")));
    }

    private static void eventRules() {
        BrainRequests requests = new BrainRequests("usr_ali", "brain", 4);
        check("first event is new", !requests.alreadySeen("evt_1"));
        check("duplicate event is seen", requests.alreadySeen("evt_1"));

        Map<String, Object> mine = event("evt_2", "usr_ali", "corr_1");
        Map<String, Object> foreign = event("evt_3", "usr_b", "corr_1");
        check("own event matches", requests.belongsToUser(mine));
        check("foreign event filtered", !requests.belongsToUser(foreign));
        check("correlation id read", "corr_1".equals(BrainRequests.correlationId(mine)));
    }

    private static void methodTable() {
        List<String> methods = BrainRequests.knownMethods();
        check("method count is 17", methods.size() == 17);
        check("resolve_person present", methods.contains("resolve_person"));
        check("people_timeline present", methods.contains("people_timeline"));

        Map<String, Object> params = Json.object();
        params.put("name", "Ali");
        Map<String, Object> envelope = new BrainRequests("usr_ali", "brain", 8)
                .request("resolve_person", params, "brain-1");
        check("envelope method", "resolve_person".equals(envelope.get("method")));
        check("envelope version", "v1".equals(envelope.get("version")));
        @SuppressWarnings("unchecked")
        Map<String, Object> body = (Map<String, Object>) envelope.get("params");
        check("identity injected", "usr_ali".equals(body.get("user_id")));
    }

    private static void liveRoundTrip(String baseUrl, String userId) {
        BrainHttpClient client = BrainClient.http(baseUrl, userId);
        Map<String, Object> health = client.health();
        check("health status", "ok".equals(Json.optString(health, "status")));
        check("health version", "v1".equals(Json.optString(health, "api_version")));

        Object ping = client.call("ping", new LinkedHashMap<>());
        check("ping result", ping instanceof Map);

        Map<String, Object> timelineParams = Json.object();
        timelineParams.put("name", "Self Check");
        @SuppressWarnings("unchecked")
        Map<String, Object> resolution = (Map<String, Object>) client.call("resolve_person", timelineParams);
        check("resolve created", Boolean.TRUE.equals(resolution.get("created")));
        check("resolve id", Json.optString(resolution, "person_id") != null);
    }

    private static Map<String, Object> event(String id, String userId, String correlationId) {
        Map<String, Object> payload = Json.object();
        payload.put("correlation_id", correlationId);
        Map<String, Object> event = Json.object();
        event.put("id", id);
        event.put("user_id", userId);
        event.put("type", "memory.created");
        event.put("payload", payload);
        return event;
    }

    private static void expectParseFailure(String label, String text) {
        try {
            Json.parse(text);
            fail(label);
        } catch (RuntimeException expected) {
            check(label, true);
        }
    }

    private static void expectObjectParseFailure(String label, String text) {
        try {
            Json.parseObject(text);
            fail(label);
        } catch (RuntimeException expected) {
            check(label, true);
        }
    }

    private static void check(String label, boolean condition) {
        if (condition) {
            System.out.println("ok   " + label);
        } else {
            fail(label);
        }
    }

    private static void fail(String label) {
        System.out.println("FAIL " + label);
        failures++;
    }
}
