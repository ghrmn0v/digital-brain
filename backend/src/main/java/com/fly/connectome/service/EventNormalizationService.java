package com.fly.connectome.service;

import java.util.HashMap;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

import org.springframework.stereotype.Service;

import com.fly.connectome.dto.EventRequest;

@Service
public class EventNormalizationService {

    private static final Set<String> KNOWN_EVENTS = Set.of(
            "important_message",
            "notification",
            "user_message",
            "task_reminder",
            "calendar_event",
            "process_completed",
            "process_failed",
            "warning",
            "app_open",
            "app_idle",
            "unknown");

    private static final Set<String> KNOWN_SOURCES = Set.of(
            "whatsapp", "core_brain", "calendar", "tasks", "linkedin", "app", "connectors", "unknown");

    /**
     * Accepts two event shapes.
     *
     * Fly's own shape names a behaviour directly ({@code event} + {@code priority}).
     * The platform shape that Product sends is a normalized event instead
     * ({@code type} + {@code payload} + {@code metadata}) and carries no priority,
     * so it gets the neutral default and its payload is preserved as context.
     *
     * A {@code type} that names no known behaviour normalizes to {@code unknown},
     * exactly as an unrecognised {@code event} always has. Guessing a behaviour
     * from a foreign event name would drive real decisions on a guess.
     */
    public EventRequest.Normalized normalize(EventRequest request) {
        String rawName = request.eventName();
        String name = isKnown(rawName, KNOWN_EVENTS) ? rawName : "unknown";
        String source = isKnown(request.source(), KNOWN_SOURCES) ? request.source() : "unknown";
        double priority = request.priority() == null
                ? EventRequest.NEUTRAL_PRIORITY
                : Math.max(0.0, Math.min(1.0, request.priority()));
        Map<String, Object> context = new HashMap<>(request.context() == null ? Map.of() : request.context());
        if (request.payload() != null) {
            context.putIfAbsent("payload", request.payload());
        }
        context.putIfAbsent("urgency", "unknown");
        return new EventRequest.Normalized(
                request.id() == null ? UUID.randomUUID().toString() : request.id(),
                name,
                source,
                priority,
                Map.copyOf(context),
                request.person());
    }

    private static boolean isKnown(String value, Set<String> known) {
        return value != null && known.contains(value);
    }
}
