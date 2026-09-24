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

import com.fly.connectome.api.WhatsAppWebhookController;
import com.fly.connectome.dto.BehaviorDecision;
import com.fly.connectome.gateway.BehaviorGateway;
import com.fly.connectome.service.WhatsAppEventMapper;
import com.fly.connectome.ws.FlyBroadcaster;

@WebMvcTest(WhatsAppWebhookController.class)
class WhatsAppWebhookControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private WhatsAppEventMapper mapper;

    @MockBean
    private BehaviorGateway gateway;

    @MockBean
    private FlyBroadcaster broadcaster;

    private static final com.fly.connectome.dto.EventRequest.Normalized IMAGE_EVENT =
            new com.fly.connectome.dto.EventRequest.Normalized(
                    "evt_wa_1", "notification", "whatsapp", 0.75,
                    Map.of("sender_name", "Sado", "media_type", "image"), null);

    @Test
    void webhookTranslatesToDecision() throws Exception {
        when(mapper.map(any())).thenReturn(IMAGE_EVENT);
        when(gateway.decide(IMAGE_EVENT)).thenReturn(new BehaviorDecision(
                null, "notification", "whatsapp", 0.75, "ATTENTION", "LOW", 0.5, Map.of(), false));

        mockMvc.perform(post("/api/v1/whatsapp/webhook")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"sender":"+994501112233","senderName":"Sado","body":"hi","type":"image","timestamp":1758700000}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.fetch").value("ATTENTION"))
                .andExpect(jsonPath("$.behaviorId").isNotEmpty());
    }

    @Test
    void webhookRejectsMissingType() throws Exception {
        mockMvc.perform(post("/api/v1/whatsapp/webhook")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"sender":"x","body":"hi","timestamp":1}
                                """))
                .andExpect(status().isBadRequest());
    }

    @Test
    void probeEndpointIsActive() throws Exception {
        mockMvc.perform(get("/api/v1/whatsapp/webhook"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("active"));
    }
}