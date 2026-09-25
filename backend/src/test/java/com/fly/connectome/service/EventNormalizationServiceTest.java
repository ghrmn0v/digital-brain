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

    /** The exact body Product's delivery adapter sends for a normalized event. */
    private static EventRequest platformEvent(String type, Map<String, Object> payload) {
        return new EventRequest(
                "integ_1", null, null, "linkedin", null, null, "2026-09-24T13:00:00.000Z", type, payload);
    }

    @Test
    void platformEventIsAcceptedAndKeepsItsId() {
        EventRequest.Normalized normalized = service.normalize(
                platformEvent("job.discovered", Map.of("jobId", "job_1")));

        assertThat(normalized.id()).isEqualTo("integ_1");
        assertThat(normalized.source()).isEqualTo("linkedin");
    }

    @Test
    void platformEventWithoutPriorityGetsTheNeutralDefault() {
        assertThat(service.normalize(platformEvent("job.discovered", null)).priority())
                .isEqualTo(EventRequest.NEUTRAL_PRIORITY);
    }

    @Test
    void platformPayloadSurvivesAsContext() {
        EventRequest.Normalized normalized = service.normalize(
                platformEvent("job.discovered", Map.of("jobId", "job_1")));

        assertThat(normalized.context()).containsKey("payload");
        assertThat(normalized.context().get("payload")).isEqualTo(Map.of("jobId", "job_1"));
    }

    @Test
    void unknownPlatformTypeNormalizesToUnknownRatherThanGuessing() {
        assertThat(service.normalize(platformEvent("job.discovered", null)).name()).isEqualTo("unknown");
        assertThat(service.normalize(platformEvent("source.linkedin.job_discovered", null)).name())
                .isEqualTo("unknown");
    }

    @Test
    void flysOwnEventNameWinsOverThePlatformType() {
        EventRequest both = new EventRequest(
                "id_2", 0.9, "important_message", "whatsapp", null, null, null,
                "job.discovered", null);

        assertThat(service.normalize(both).name()).isEqualTo("important_message");
        assertThat(service.normalize(both).priority()).isEqualTo(0.9);
    }

    @Test
    void eventIdentifiedRuleAcceptsEitherField() {
        assertThat(new EventRequest("i", null, "notification", "app", null, null, null).isEventIdentified())
                .isTrue();
        assertThat(new EventRequest("i", null, null, "app", null, null, null, "job.discovered", null)
                .isEventIdentified()).isTrue();
        assertThat(new EventRequest("i", null, null, "app", null, null, null, null, null).isEventIdentified())
                .isFalse();
    }

    @Test
    void missingEventAndTypeFallsBackToUnknownInsteadOfFailing() {
        EventRequest.Normalized normalized = service.normalize(
                new EventRequest("id_3", null, null, "app", null, null, null, null, null));

        assertThat(normalized.name()).isEqualTo("unknown");
        assertThat(normalized.priority()).isEqualTo(EventRequest.NEUTRAL_PRIORITY);
    }

    @Test
    void missingIdIsGenerated() {
        EventRequest withoutId = new EventRequest(null, 0.4, "notification", "app", null, null, null);

        assertThat(service.normalize(withoutId).id()).isNotNull().isNotEqualTo("id_1");
    }
}