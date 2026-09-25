package com.fly.connectome.api;

import java.util.List;
import java.util.Map;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.fly.connectome.dto.BehaviorDecision;
import com.fly.connectome.dto.EventRequest;
import com.fly.connectome.dto.FeedbackRequest;
import com.fly.connectome.dto.HealthResponse;
import com.fly.connectome.gateway.BehaviorGateway;
import com.fly.connectome.service.EventNormalizationService;
import com.fly.connectome.ws.FlyBroadcaster;

import jakarta.validation.Valid;

@RestController
@RequestMapping("/api/v1")
public class FlyController {

    private final EventNormalizationService normalization;
    private final BehaviorGateway gateway;
    private final FlyBroadcaster broadcaster;

    public FlyController(EventNormalizationService normalization, BehaviorGateway gateway, FlyBroadcaster broadcaster) {
        this.normalization = normalization;
        this.gateway = gateway;
        this.broadcaster = broadcaster;
    }

    @PostMapping("/events")
    public ResponseEntity<BehaviorDecision> processEvent(@Valid @RequestBody EventRequest request) {
        EventRequest.Normalized event = normalization.normalize(request);
        BehaviorDecision decision = gateway.decide(event).withBehaviorId(event.id());
        broadcaster.broadcast(Map.of(
                "type", "fly_behavior",
                "behavior_id", decision.behaviorId(),
                "decision", decision,
                "context", event.context()));
        return ResponseEntity.ok(decision);
    }

    @PostMapping("/feedback")
    public ResponseEntity<Map<String, Object>> feedback(@Valid @RequestBody FeedbackRequest request) {
        Map<String, Object> result = gateway.applyFeedback(request);
        broadcaster.broadcast(Map.of("type", "fly_feedback_result", "result", result));
        return ResponseEntity.ok(result);
    }

    @GetMapping("/health")
    public ResponseEntity<HealthResponse> health() {
        Map<String, Object> python = gateway.health();
        boolean reachable = Boolean.TRUE.equals(python.get("reachable"));
        HealthResponse response = reachable
                ? HealthResponse.up("UP", python)
                : HealthResponse.degraded("DOWN", python);
        return ResponseEntity.ok(response);
    }

    @GetMapping("/states")
    public ResponseEntity<Map<String, Object>> states() {
        return ResponseEntity.ok(gateway.states());
    }

    @GetMapping("/mode/flight")
    public ResponseEntity<Map<String, Object>> flightMode() {
        return ResponseEntity.ok(gateway.flightMode());
    }

    @PostMapping("/mode/flight")
    public ResponseEntity<Map<String, Object>> setFlight(@RequestBody Map<String, Object> body) {
        boolean enabled = Boolean.TRUE.equals(body.get("flight"));
        return ResponseEntity.ok(gateway.setFlight(enabled));
    }

    @GetMapping("/events/contract")
    public ResponseEntity<Map<String, Object>> contract() {
        return ResponseEntity.ok(Map.of(
                "direction", "core_brain/connectors -> connectome -> behavior engine",
                "shapes", List.of(
                        Map.of(
                                "name", "fly",
                                "description", "Fly's own event, naming a behaviour directly",
                                "required", List.of("source", "event or type"),
                                "example", Map.ofEntries(
                                        Map.entry("event", "important_message"),
                                        Map.entry("source", "whatsapp"),
                                        Map.entry("priority", 0.85),
                                        Map.entry("person", Map.of("id", "person_123")),
                                        Map.entry("context", Map.of("topic", "job", "urgency", "high")),
                                        Map.entry("timestamp", "2026-09-24T13:00:00Z"))),
                        Map.of(
                                "name", "platform_normalized",
                                "description", "Normalized event as sent by Product's delivery adapter. "
                                        + "It carries no priority, so a neutral "
                                        + EventRequest.NEUTRAL_PRIORITY + " is used, and its payload is "
                                        + "preserved as context.payload.",
                                "required", List.of("source", "event or type"),
                                "example", Map.ofEntries(
                                        Map.entry("id", "integ_1"),
                                        Map.entry("type", "job.discovered"),
                                        Map.entry("source", "linkedin"),
                                        Map.entry("timestamp", "2026-09-24T13:00:00.000Z"),
                                        Map.entry("payload", Map.of("jobId", "job_1")),
                                        Map.entry("metadata", Map.of("schemaVersion", "1.0"))))),
                "notes", List.of(
                        "event or type identifies the event; Fly's own event field wins when both are sent.",
                        "A type naming no known behaviour normalizes to unknown; Fly never guesses a behaviour.",
                        "Unknown sources normalize to unknown."),
                "version", "v1"));
    }
}