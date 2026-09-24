package com.fly.connectome;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.util.Map;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import com.fly.connectome.api.FlyController;
import com.fly.connectome.dto.BehaviorDecision;
import com.fly.connectome.dto.EventRequest;
import com.fly.connectome.gateway.BehaviorGateway;
import com.fly.connectome.service.EventNormalizationService;
import com.fly.connectome.ws.FlyBroadcaster;

@WebMvcTest(FlyController.class)
class FlyControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private EventNormalizationService normalization;

    @MockBean
    private BehaviorGateway gateway;

    @MockBean
    private FlyBroadcaster broadcaster;

    private static final EventRequest.Normalized IMPORTANT = new EventRequest.Normalized(
            "evt_1", "important_message", "whatsapp", 0.9, Map.of("urgency", "high"), null);

    @Test
    void acceptsValidEventAndReturnsDecision() throws Exception {
        when(normalization.normalize(any())).thenReturn(IMPORTANT);
        when(gateway.decide(IMPORTANT)).thenReturn(new BehaviorDecision(
                "important_message", "whatsapp", 0.9, "IMPORTANT", "HIGH", 0.44, Map.of(), false));

        mockMvc.perform(post("/api/v1/events")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"event":"important_message","source":"whatsapp","priority":0.9,"context":{"topic":"job"}}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.fetch").value("IMPORTANT"))
                .andExpect(jsonPath("$.priorityLevel").value("HIGH"))
                .andExpect(jsonPath("$.fallback").value(false));
    }

    @Test
    void rejectsInvalidPayloadWith400() throws Exception {
        mockMvc.perform(post("/api/v1/events")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"event":"important_message"}
                                """))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("validation_failed"));
    }

    @Test
    void feedbackRequiresFields() throws Exception {
        mockMvc.perform(post("/api/v1/feedback")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{}"))
                .andExpect(status().isBadRequest());
    }

    @Test
    void healthIsUpWhenPythonReachable() throws Exception {
        when(gateway.health()).thenReturn(Map.of(
                "status", "ok", "service", "fly-python-behavior", "graph", "adult_drosophila_mushroom_body", "neurons", 2414, "reachable", true));

        mockMvc.perform(get("/api/v1/health"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("UP"))
                .andExpect(jsonPath("$.python").value("UP"));
    }

    @Test
    void healthIsDegradedWhenPythonDown() throws Exception {
        when(gateway.health()).thenReturn(Map.of("status", "DOWN", "reason", "unreachable"));

        mockMvc.perform(get("/api/v1/health"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("DEGRADED"))
                .andExpect(jsonPath("$.python").value("DOWN"));
    }

    @Test
    void contractEndpointDocumentsSchema() throws Exception {
        mockMvc.perform(get("/api/v1/events/contract"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.version").value("v1"))
                .andExpect(jsonPath("$.example.priority").value(0.85));
    }
}