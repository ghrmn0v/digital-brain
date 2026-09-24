package com.fly.connectome.dto;

import java.util.Map;

public record BehaviorDecision(
        String event,
        String source,
        double priority,
        String fetch,
        String priorityLevel,
        double confidence,
        Map<String, Double> activity,
        boolean fallback) {

    public static BehaviorDecision fallback(String event, String source, double priority, String fetch, String priorityLevel) {
        return new BehaviorDecision(event, source, priority, fetch, priorityLevel, 0.0, Map.of(), true);
    }
}