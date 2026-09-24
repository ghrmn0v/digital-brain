package com.fly.connectome.gateway;

import java.net.URI;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Map;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fly.connectome.config.PythonProperties;
import com.fly.connectome.dto.BehaviorDecision;
import com.fly.connectome.dto.EventRequest;
import com.fly.connectome.dto.FeedbackRequest;

@Component
public class BehaviorGateway {

    private static final Logger log = LoggerFactory.getLogger(BehaviorGateway.class);

    private final RestClient client;
    private final ObjectMapper mapper;
    private final FallbackPolicy fallback;
    private final URI behaviorUri;
    private final URI feedbackUri;
    private final URI healthUri;

    public BehaviorGateway(PythonProperties properties, ObjectMapper mapper, FallbackPolicy fallback) {
        this.mapper = mapper;
        this.fallback = fallback;
        String base = properties.baseUrl();
        this.behaviorUri = URI.create(base + "/behavior");
        this.feedbackUri = URI.create(base + "/feedback");
        this.healthUri = URI.create(base + "/health");
        this.client = RestClient.builder()
                .baseUrl(base)
                .requestFactory(settings(properties.connectTimeout(), properties.readTimeout()))
                .build();
    }

    private static org.springframework.http.client.ClientHttpRequestFactory settings(Duration connect, Duration read) {
        org.springframework.http.client.SimpleClientHttpRequestFactory factory =
                new org.springframework.http.client.SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(connect);
        factory.setReadTimeout(read);
        return factory;
    }

    public BehaviorDecision decide(EventRequest.Normalized event) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("id", event.id());
        body.put("event", event.name());
        body.put("source", event.source());
        body.put("priority", event.priority());
        body.put("context", event.context());
        body.put("person", event.person());
        try {
            String payload = mapper.writeValueAsString(body);
            JsonNode node = client.post()
                    .uri("/behavior")
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(payload)
                    .retrieve()
                    .body(JsonNode.class);
            if (node == null || node.hasNonNull("error")) {
                throw new IllegalStateException("python returned an error for " + event.name());
            }
            return new BehaviorDecision(
                    text(node, "event"),
                    text(node, "source"),
                    node.path("priority").asDouble(event.priority()),
                    text(node, "fetch"),
                    text(node, "priority_level"),
                    node.path("confidence").asDouble(0.0),
                    node.path("activity").isMissingNode() ? Map.of() : mapper.convertValue(node.path("activity"), Map.class),
                    false);
        } catch (Exception exc) {
            log.warn("behavior decision from python failed: {}", exc.getMessage());
            return fallback.decide(event, exc.getClass().getSimpleName());
        }
    }

    public Map<String, Object> applyFeedback(FeedbackRequest request) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("behavior_id", request.behaviorId());
        body.put("feedback", request.feedback());
        try {
            String payload = mapper.writeValueAsString(body);
            JsonNode node = client.post()
                    .uri("/feedback")
                    .contentType(MediaType.APPLICATION_JSON)
                    .body(payload)
                    .retrieve()
                    .body(JsonNode.class);
            if (node == null) {
                throw new IllegalStateException("empty python response");
            }
            return mapper.convertValue(node, Map.class);
        } catch (Exception exc) {
            log.warn("feedback delivery failed: {}", exc.getMessage());
            return Map.of("error", "python_unavailable", "detail", exc.getClass().getSimpleName());
        }
    }

    public Map<String, Object> health() {
        try {
            JsonNode node = client.get()
                    .uri("/health")
                    .retrieve()
                    .body(JsonNode.class);
            if (node == null) {
                throw new IllegalStateException("empty health response");
            }
            Map<String, Object> details = mapper.convertValue(node, Map.class);
            details.put("reachable", true);
            return details;
        } catch (ResourceAccessException exc) {
            log.info("python health probe failed: {}", exc.getMessage());
            return fallback.pythonDownHealth();
        } catch (Exception exc) {
            log.info("python health probe degraded: {}", exc.getMessage());
            return fallback.pythonDownHealth();
        }
    }

    public Map<String, Object> states() {
        try {
            JsonNode node = client.get()
                    .uri("/states")
                    .retrieve()
                    .body(JsonNode.class);
            if (node == null || node.path("states").isMissingNode()) {
                throw new IllegalStateException("empty states response");
            }
            return Map.of("source", "python", "states", mapper.convertValue(node.path("states"), java.util.List.class));
        } catch (Exception exc) {
            log.info("python states probe failed: {}", exc.getMessage());
            return Map.of(
                    "source", "fallback",
                    "states", java.util.List.of(),
                    "error", exc.getClass().getSimpleName());
        }
    }

    private static String text(JsonNode node, String field) {
        return node.path(field).asText("unknown");
    }
}