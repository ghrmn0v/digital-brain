package com.fly.connectome.dto;

import java.time.Instant;
import java.util.Map;

public record ApiError(
        String code,
        String message,
        Map<String, String> details,
        String timestamp) {

    public static ApiError of(String code, String message, Map<String, String> details) {
        return new ApiError(code, message, details, Instant.now().toString());
    }
}