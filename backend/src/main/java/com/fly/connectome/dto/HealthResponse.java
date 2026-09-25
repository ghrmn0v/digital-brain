package com.fly.connectome.dto;

import java.util.Map;

public record HealthResponse(
        String status,
        String python,
        Map<String, Object> components) {

    public static HealthResponse up(String pythonStatus, Map<String, Object> pythonDetails) {
        return new HealthResponse("UP", pythonStatus, Map.of("python", pythonDetails));
    }

    public static HealthResponse degraded(String pythonStatus, Map<String, Object> pythonDetails) {
        return new HealthResponse("DEGRADED", pythonStatus, Map.of("python", pythonDetails));
    }
}