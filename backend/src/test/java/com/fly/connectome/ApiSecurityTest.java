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
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import com.fly.connectome.api.FlyController;
import com.fly.connectome.config.ApiSecurityConfig;
import com.fly.connectome.dto.BehaviorDecision;
import com.fly.connectome.dto.EventRequest;
import com.fly.connectome.gateway.BehaviorGateway;
import com.fly.connectome.service.EventNormalizationService;
import com.fly.connectome.ws.FlyBroadcaster;

@WebMvcTest(controllers = FlyController.class, properties = "app.security.api-token=top-secret")
@Import(ApiSecurityConfig.class)
class ApiSecurityTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private EventNormalizationService normalization;

    @MockBean
    private BehaviorGateway gateway;

    @MockBean
    private FlyBroadcaster broadcaster;

    @Test
    void postWithoutTokenIsUnauthorized() throws Exception {
        mockMvc.perform(post("/api/v1/events")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"event\":\"important_message\"}"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("unauthorized"));
    }

    @Test
    void postWithWrongTokenIsUnauthorized() throws Exception {
        mockMvc.perform(post("/api/v1/events")
                        .header("X-Fly-Token", "wrong")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"event\":\"important_message\"}"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void postWithMatchingTokenPassesThrough() throws Exception {
        EventRequest.Normalized event = new EventRequest.Normalized(
                "evt_1", "important_message", "whatsapp", 0.9, Map.of(), null);
        when(normalization.normalize(any())).thenReturn(event);
        when(gateway.decide(any())).thenReturn(new BehaviorDecision(
                null, "important_message", "whatsapp", 0.9, "IMPORTANT", "HIGH", 0.44, Map.of(), false));

        mockMvc.perform(post("/api/v1/events")
                        .header("X-Fly-Token", "top-secret")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"event\":\"important_message\",\"source\":\"whatsapp\",\"priority\":0.9}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.fetch").value("IMPORTANT"));
    }

    @Test
    void getsRemainOpen() throws Exception {
        when(gateway.health()).thenReturn(Map.of(
                "status", "ok", "service", "fly-python-behavior", "neurons", 2414, "reachable", true));

        mockMvc.perform(get("/api/v1/health"))
                .andExpect(status().isOk());
    }
}