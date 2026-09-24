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

    public EventRequest.Normalized normalize(EventRequest request) {
        String name = KNOWN_EVENTS.contains(request.event()) ? request.event() : "unknown";
        String source = KNOWN_SOURCES.contains(request.source()) ? request.source() : "unknown";
        double priority = Math.max(0.0, Math.min(1.0, request.priority()));
        Map<String, Object> context = new HashMap<>(request.context() == null ? Map.of() : request.context());
        context.putIfAbsent("urgency", "unknown");
        return new EventRequest.Normalized(
                request.id() == null ? UUID.randomUUID().toString() : request.id(),
                name,
                source,
                priority,
                Map.copyOf(context),
                request.person());
    }
}