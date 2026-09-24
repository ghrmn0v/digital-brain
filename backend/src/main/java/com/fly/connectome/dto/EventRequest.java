package com.fly.connectome.dto;

import java.util.Map;

import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.PositiveOrZero;

public record EventRequest(
        String id,
        @NotNull @DecimalMin("0.0") @DecimalMax("1.0") Double priority,
        @NotBlank String event,
        @NotBlank String source,
        Map<String, Object> context,
        Map<String, Object> person,
        String timestamp) {

    public record Normalized(
            String id,
            String name,
            String source,
            double priority,
            Map<String, Object> context,
            Map<String, Object> person) {
    }
}