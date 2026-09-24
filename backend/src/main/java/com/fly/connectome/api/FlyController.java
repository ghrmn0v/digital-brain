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
        BehaviorDecision decision = gateway.decide(event).withBehaviorId("behavior_" + event.id());
        broadcaster.broadcast(Map.of(
                "type", "fly_behavior",
                "behavior_id", decision.behaviorId(),
                "decision", decision));
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

    @GetMapping("/events/contract")
    public ResponseEntity<Map<String, Object>> contract() {
        return ResponseEntity.ok(Map.of(
                "direction", "core_brain/connectors -> connectome -> behavior engine",
                "example", Map.ofEntries(
                        Map.entry("event", "important_message"),
                        Map.entry("source", "whatsapp"),
                        Map.entry("priority", 0.85),
                        Map.entry("person", Map.of("id", "person_123")),
                        Map.entry("context", Map.of("topic", "job", "urgency", "high")),
                        Map.entry("timestamp", "2026-09-24T13:00:00Z")),
                "version", "v1"));
    }
}