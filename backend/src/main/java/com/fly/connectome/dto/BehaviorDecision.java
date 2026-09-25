package com.fly.connectome.dto;

import java.util.Map;

public record BehaviorDecision(
        String behaviorId,
        String event,
        String source,
        double priority,
        String fetch,
        String priorityLevel,
        double confidence,
        Map<String, Double> activity,
        boolean fallback) {

    public static BehaviorDecision fallback(EventRequest.Normalized event, String fetch, String priorityLevel) {
        return new BehaviorDecision(
                null, event.name(), event.source(), event.priority(), fetch, priorityLevel, 0.0, Map.of(), true);
    }

    public BehaviorDecision withBehaviorId(String behaviorId) {
        if (behaviorId == null || this.behaviorId != null) {
            return this;
        }
        return new BehaviorDecision(behaviorId, event, source, priority, fetch, priorityLevel, confidence, activity, fallback);
    }
}