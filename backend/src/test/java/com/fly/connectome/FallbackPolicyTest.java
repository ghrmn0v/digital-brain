package com.fly.connectome;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

import com.fly.connectome.dto.EventRequest;
import com.fly.connectome.dto.BehaviorDecision;
import com.fly.connectome.gateway.FallbackPolicy;

class FallbackPolicyTest {

    private final FallbackPolicy fallback = new FallbackPolicy();

    private EventRequest.Normalized event(String name, double priority) {
        return new EventRequest.Normalized("id", name, "whatsapp", priority, java.util.Map.of(), null);
    }

    @Test
    void replacesImportantMessageWithImportant() {
        BehaviorDecision decision = fallback.decide(event("important_message", 0.9), "test");
        assertEquals("IMPORTANT", decision.fetch());
        assertEquals("HIGH", decision.priorityLevel());
        assertEquals(true, decision.fallback());
    }

    @Test
    void highPriorityUnknownEscalatesToImportant() {
        BehaviorDecision decision = fallback.decide(event("unknown", 0.9), "test");
        assertEquals("IMPORTANT", decision.fetch());
    }

    @Test
    void lowPriorityUnknownFallsToIdle() {
        BehaviorDecision decision = fallback.decide(event("unknown", 0.1), "test");
        assertEquals("IDLE", decision.fetch());
    }

    @Test
    void failedProcessMapsToError() {
        BehaviorDecision decision = fallback.decide(event("process_failed", 0.5), "test");
        assertEquals("ERROR", decision.fetch());
        assertEquals("CRITICAL", decision.priorityLevel());
    }
}