package com.fly.connectome.gateway;

import java.util.Map;

import org.springframework.stereotype.Component;

import com.fly.connectome.dto.BehaviorDecision;
import com.fly.connectome.dto.EventRequest;

@Component
public class FallbackPolicy {

    public BehaviorDecision decide(EventRequest.Normalized event, String reason) {
        String fetch = switch (event.name()) {
            case "important_message", "calendar_event" -> "IMPORTANT";
            case "warning" -> "WARNING";
            case "process_failed" -> "ERROR";
            case "process_completed" -> "SUCCESS";
            case "user_message" -> "LISTENING";
            case "task_reminder", "notification" -> "ATTENTION";
            case "app_open" -> "CURIOUS";
            case "app_idle" -> "IDLE";
            default -> event.priority() >= 0.7 ? "IMPORTANT" : "IDLE";
        };
        String level = switch (fetch) {
            case "WARNING", "ERROR" -> "CRITICAL";
            case "IMPORTANT", "WAITING", "SUCCESS" -> "HIGH";
            case "THINKING", "PROCESSING", "LEARNING" -> "MEDIUM";
            case "ATTENTION", "CURIOUS", "LISTENING" -> "LOW";
            default -> "BACKGROUND";
        };
        return BehaviorDecision.fallback(event, fetch, level);
    }

    public Map<String, Object> pythonDownHealth() {
        return Map.of(
                "status", "DOWN",
                "reason", "behavior engine unreachable; rule-based fallback active");
    }
}