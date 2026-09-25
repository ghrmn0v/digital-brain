package com.fly.connectome;

import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.util.Map;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import com.fly.connectome.api.DeveloperController;
import com.fly.connectome.service.DeveloperEventMapper;
import com.fly.connectome.service.DeveloperLocationMapper;
import com.fly.connectome.service.DeveloperModeService;
import com.fly.connectome.ws.FlyBroadcaster;

@WebMvcTest(DeveloperController.class)
@Import({DeveloperModeService.class, DeveloperEventMapper.class, DeveloperLocationMapper.class})
class DeveloperControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private DeveloperModeService mode;

    @MockBean
    private FlyBroadcaster broadcaster;

    @BeforeEach
    void resetMode() {
        mode.setEnabled(false);
    }

    private static final String VALID_BUG_EVENT = """
            {
              "type": "developer.bug_detected",
              "eventId": "dev_evt_1",
              "repository": "companion-app",
              "file": "src/auth/login.ts",
              "line": 42,
              "column": 10,
              "title": "Possible null reference",
              "message": "user may be undefined before accessing user.email",
              "severity": "warning"
            }
            """;

    private void enableMode() throws Exception {
        mockMvc.perform(post("/api/v1/developer/mode")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"enabled\":true}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.enabled").value(true));
    }

    @Test
    void modeIsOffByDefault() throws Exception {
        mockMvc.perform(get("/api/v1/developer/mode"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.enabled").value(false));
    }

    @Test
    void modeCanBeToggledThroughApi() throws Exception {
        enableMode();
        mockMvc.perform(get("/api/v1/developer/mode"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.enabled").value(true));

        mockMvc.perform(post("/api/v1/developer/mode")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"enabled\":false}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.enabled").value(false));
    }

    @Test
    void eventIsIgnoredWhenModeOffAndNeverBroadcast() throws Exception {
        mockMvc.perform(post("/api/v1/developer/events")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(VALID_BUG_EVENT))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("ignored"))
                .andExpect(jsonPath("$.reason").value("developer_mode_off"))
                .andExpect(jsonPath("$.type").value("developer.bug_detected"));

        verifyNoInteractions(broadcaster);
    }

    @Test
    @SuppressWarnings({"unchecked", "rawtypes"})
    void validBugEventIsProcessedAndMessagePassedUnchanged() throws Exception {
        enableMode();

        mockMvc.perform(post("/api/v1/developer/events")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(VALID_BUG_EVENT))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("processed"))
                .andExpect(jsonPath("$.decision.fetch").value("WARNING"))
                .andExpect(jsonPath("$.decision.priorityLevel").value("HIGH"))
                .andExpect(jsonPath("$.developer.type").value("developer.bug_detected"))
                .andExpect(jsonPath("$.developer.message").value("user may be undefined before accessing user.email"))
                .andExpect(jsonPath("$.developer.anchor").isNotEmpty())
                .andExpect(jsonPath("$.developer.mapped").value(true))
                .andExpect(jsonPath("$.developer.bubble_ms").isNumber());

        ArgumentCaptor<Map> payload = ArgumentCaptor.forClass(Map.class);
        verify(broadcaster).broadcast(payload.capture());
        Map context = (Map) payload.getValue().get("context");
        Map developer = (Map) context.get("developer");
        // Fly must not rewrite Brain text, even over the wire.
        assert developer.get("message").equals("user may be undefined before accessing user.email");
    }

    @Test
    void missingRequiredFieldsAreRejectedWith400() throws Exception {
        enableMode();

        mockMvc.perform(post("/api/v1/developer/events")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"type":"developer.bug_detected","repository":"r","file":"f","severity":"warning"}
                                """))
                .andExpect(status().isBadRequest());

        mockMvc.perform(post("/api/v1/developer/events")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"repository":"r","file":"f","message":"m","severity":"warning"}
                                """))
                .andExpect(status().isBadRequest());

        mockMvc.perform(post("/api/v1/developer/events")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"type":"developer.bug_detected","file":"f","message":"m"}
                                """))
                .andExpect(status().isBadRequest());
    }

    @Test
    void reservedAndUnknownEventTypesAreIgnored() throws Exception {
        enableMode();

        mockMvc.perform(post("/api/v1/developer/events")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"type":"developer.fix_proposed","repository":"r","file":"f","message":"m","severity":"warning"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("ignored"))
                .andExpect(jsonPath("$.reason").value("event_type_not_implemented"));

        mockMvc.perform(post("/api/v1/developer/events")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"type":"foo.bar","repository":"r","file":"f","message":"m","severity":"warning"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("ignored"))
                .andExpect(jsonPath("$.reason").value("unsupported_event_type"));

        verify(broadcaster, never()).broadcast(org.mockito.ArgumentMatchers.any());
    }

    @Test
    @SuppressWarnings({"unchecked", "rawtypes"})
    void behaviorIdEqualsProvidedEventIdForFeedbackLinkage() throws Exception {
        enableMode();

        mockMvc.perform(post("/api/v1/developer/events")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(VALID_BUG_EVENT))
                .andExpect(status().isOk());

        ArgumentCaptor<Map> payload = ArgumentCaptor.forClass(Map.class);
        verify(broadcaster).broadcast(payload.capture());
        assert payload.getValue().get("behavior_id").equals("dev_evt_1");
    }

    @Test
    void severityMapsToStateAndLevel() throws Exception {
        enableMode();

        mockMvc.perform(post("/api/v1/developer/events")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"type":"developer.bug_detected","repository":"r","file":"f","message":"boom","severity":"error"}
                                """))
                .andExpect(jsonPath("$.decision.fetch").value("ERROR"))
                .andExpect(jsonPath("$.decision.priorityLevel").value("CRITICAL"));

        mockMvc.perform(post("/api/v1/developer/events")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"type":"developer.bug_detected","repository":"r","file":"f","message":"note","severity":"info"}
                                """))
                .andExpect(jsonPath("$.decision.fetch").value("ATTENTION"))
                .andExpect(jsonPath("$.decision.priorityLevel").value("LOW"));
    }

    @Test
    void contractDocumentsSupportedAndReservedTypes() throws Exception {
        mockMvc.perform(get("/api/v1/developer/contract"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.version").value("v1"))
                .andExpect(jsonPath("$.supported[0]").value("developer.bug_detected"))
                .andExpect(jsonPath("$.reserved").isArray())
                .andExpect(jsonPath("$.example.file").value("src/auth/login.ts"));
    }
}