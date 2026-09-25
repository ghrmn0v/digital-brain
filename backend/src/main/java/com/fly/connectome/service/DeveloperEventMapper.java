package com.fly.connectome.service;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import com.fly.connectome.dto.BehaviorDecision;
import com.fly.connectome.dto.DeveloperEventRequest;

/**
 * Translates a structured Core Brain developer event into a Fly decision + context.
 * The explanation text is passed through verbatim — Fly never generates or infers it.
 */
@Service
public class DeveloperEventMapper {

    public static final String BUG_DETECTED = "developer.bug_detected";

    /** Implemented now. */
    public static final Set<String> SUPPORTED_TYPES = Set.of(BUG_DETECTED);

    /** Reserved for the future; recognized but intentionally not implemented yet. */
    public static final Set<String> RESERVED_TYPES = Set.of(
            "developer.explanation",
            "developer.fix_proposed",
            "developer.test_result",
            "developer.review_finding",
            "developer.deploy_status");

    public static final Set<String> KNOWN_SEVERITIES = Set.of("info", "warning", "error");

    private final DeveloperLocationMapper locations;
    private final long bubbleMs;

    public DeveloperEventMapper(
            DeveloperLocationMapper locations,
            @Value("${app.developer.bubble-ms:7000}") long bubbleMs) {
        this.locations = locations;
        this.bubbleMs = bubbleMs;
    }

    public boolean isSupported(String type) {
        return SUPPORTED_TYPES.contains(type);
    }

    public boolean isReserved(String type) {
        return RESERVED_TYPES.contains(type);
    }

    public String severity(String raw) {
        String normalized = raw == null ? "info" : raw.toLowerCase();
        return KNOWN_SEVERITIES.contains(normalized) ? normalized : "info";
    }

    public String stateFor(String severity) {
        return switch (severity) {
            case "error" -> "ERROR";
            case "warning" -> "WARNING";
            default -> "ATTENTION";
        };
    }

    public String levelFor(String severity) {
        return switch (severity) {
            case "error" -> "CRITICAL";
            case "warning" -> "HIGH";
            default -> "LOW";
        };
    }

    public double priorityFor(String severity) {
        return switch (severity) {
            case "error" -> 0.95;
            case "warning" -> 0.75;
            default -> 0.5;
        };
    }

    public String titleFor(DeveloperEventRequest request) {
        return request.title() == null || request.title().isBlank() ? request.type() : request.title();
    }

    public BehaviorDecision toDecision(DeveloperEventRequest request) {
        String severity = severity(request.severity());
        String id = request.eventId() == null || request.eventId().isBlank()
                ? UUID.randomUUID().toString()
                : request.eventId();
        return new BehaviorDecision(
                id,
                request.type(),
                "core_brain",
                priorityFor(severity),
                stateFor(severity),
                levelFor(severity),
                1.0,
                Map.of(),
                false);
    }

    public Map<String, Object> contextFor(DeveloperEventRequest request) {
        String severity = severity(request.severity());
        DeveloperLocationMapper.Location location = locations.map(request.repository(), request.file(), request.line());
        Map<String, Object> developer = new LinkedHashMap<>();
        developer.put("type", request.type());
        developer.put("event_id", request.eventId());
        developer.put("repository", request.repository());
        developer.put("file", request.file());
        developer.put("line", request.line());
        developer.put("column", request.column());
        developer.put("title", titleFor(request));
        developer.put("message", request.message());
        developer.put("severity", severity);
        developer.put("anchor", location.anchor());
        developer.put("mapped", location.mapped());
        developer.put("bubble_ms", bubbleMs);
        return Map.of("developer", developer);
    }
}
