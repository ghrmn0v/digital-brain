package com.fly.connectome.service;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Map;

import org.junit.jupiter.api.Test;

import com.fly.connectome.dto.EventRequest;

class EventNormalizationServiceTest {

    private final EventNormalizationService service = new EventNormalizationService();

    private static EventRequest request(String event, String source, Double priority, Map<String, Object> context) {
        return new EventRequest("id_1", priority, event, source, context, null, null);
    }

    @Test
    void knownEventAndSourcePassThrough() {
        EventRequest.Normalized normalized = service.normalize(
                request("important_message", "whatsapp", 0.85, Map.of("topic", "job")));

        assertThat(normalized.name()).isEqualTo("important_message");
        assertThat(normalized.source()).isEqualTo("whatsapp");
        assertThat(normalized.priority()).isEqualTo(0.85);
    }

    @Test
    void unknownEventAndSourceBecomeUnknown() {
        EventRequest.Normalized normalized = service.normalize(
                request("random_thing", "telegram", 0.5, null));

        assertThat(normalized.name()).isEqualTo("unknown");
        assertThat(normalized.source()).isEqualTo("unknown");
    }

    @Test
    void priorityIsClampedToUnitInterval() {
        assertThat(service.normalize(request("notification", "app", 1.7, null)).priority()).isEqualTo(1.0);
        assertThat(service.normalize(request("notification", "app", -0.3, null)).priority()).isEqualTo(0.0);
    }

    @Test
    void contextGetsDefaultUrgencyAndIsImmutableCopy() {
        EventRequest.Normalized normalized = service.normalize(request("notification", "app", 0.4, null));

        assertThat(normalized.context()).containsEntry("urgency", "unknown");
        assertThat(normalized.context().get("urgency")).isEqualTo("unknown");
    }

    @Test
    void missingIdIsGenerated() {
        EventRequest withoutId = new EventRequest(null, 0.4, "notification", "app", null, null, null);

        assertThat(service.normalize(withoutId).id()).isNotNull().isNotEqualTo("id_1");
    }
}