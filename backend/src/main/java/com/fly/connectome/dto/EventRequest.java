package com.fly.connectome.dto;

import java.util.Map;

import jakarta.validation.constraints.AssertTrue;
import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;

public record EventRequest(
        String id,
        @DecimalMin("0.0") @DecimalMax("1.0") Double priority,
        String event,
        @NotBlank String source,
        Map<String, Object> context,
        Map<String, Object> person,
        String timestamp,
        String type,
        Map<String, Object> payload) {

    /**
     * The neutral priority used when a sender does not express one.
     *
     * Product's normalized events carry no priority, and inventing a ranking
     * from the payload would be a guess that changes Fly's decision thresholds.
     * A neutral default keeps every such event equally weighted.
     */
    public static final double NEUTRAL_PRIORITY = 0.5;

    /**
     * Fly's own event shape, unchanged.
     *
     * Kept so existing callers and clients of {@code /api/v1/events} continue to
     * compile and behave exactly as before.
     */
    public EventRequest(
            String id,
            Double priority,
            String event,
            String source,
            Map<String, Object> context,
            Map<String, Object> person,
            String timestamp) {
        this(id, priority, event, source, context, person, timestamp, null, null);
    }

    /**
     * An event is identified either by Fly's own {@code event} name or by the
     * platform event {@code type} that Product sends.
     *
     * Exactly one of the two is required, which a per-field annotation cannot
     * express, so the rule lives here. The message matches the
     * {@code validation_failed} body the API already returns.
     */
    @AssertTrue(message = "either event or type is required")
    public boolean isEventIdentified() {
        return isPresent(event) || isPresent(type);
    }

    /** The event name to normalize, preferring Fly's own field. */
    public String eventName() {
        return isPresent(event) ? event : type;
    }

    private static boolean isPresent(String value) {
        return value != null && !value.isBlank();
    }

    public record Normalized(
            String id,
            String name,
            String source,
            double priority,
            Map<String, Object> context,
            Map<String, Object> person) {
    }
}
