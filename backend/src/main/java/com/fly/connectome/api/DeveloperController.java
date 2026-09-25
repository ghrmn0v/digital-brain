package com.fly.connectome.api;

import java.util.LinkedHashMap;
import java.util.Map;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.fly.connectome.dto.BehaviorDecision;
import com.fly.connectome.dto.DeveloperEventRequest;
import com.fly.connectome.dto.DeveloperModeRequest;
import com.fly.connectome.service.DeveloperEventMapper;
import com.fly.connectome.service.DeveloperModeService;
import com.fly.connectome.ws.FlyBroadcaster;

import jakarta.validation.Valid;

/**
 * Brain -> Fly developer interface. Reuses the existing WS transport and behavior
 * decision shape; Core Brain supplies every piece of text.
 */
@RestController
@RequestMapping("/api/v1/developer")
public class DeveloperController {

    private final DeveloperModeService mode;
    private final DeveloperEventMapper mapper;
    private final FlyBroadcaster broadcaster;

    public DeveloperController(DeveloperModeService mode, DeveloperEventMapper mapper, FlyBroadcaster broadcaster) {
        this.mode = mode;
        this.mapper = mapper;
        this.broadcaster = broadcaster;
    }

    @PostMapping("/events")
    public ResponseEntity<Map<String, Object>> handle(@Valid @RequestBody DeveloperEventRequest request) {
        if (!mode.isEnabled()) {
            return ResponseEntity.ok(Map.of(
                    "status", "ignored",
                    "reason", "developer_mode_off",
                    "type", request.type()));
        }
        if (!mapper.isSupported(request.type())) {
            String reason = mapper.isReserved(request.type())
                    ? "event_type_not_implemented"
                    : "unsupported_event_type";
            return ResponseEntity.ok(Map.of(
                    "status", "ignored",
                    "reason", reason,
                    "type", request.type()));
        }

        BehaviorDecision decision = mapper.toDecision(request);
        Map<String, Object> context = mapper.contextFor(request);

        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("type", "developer_event");
        payload.put("behavior_id", decision.behaviorId());
        payload.put("decision", decision);
        payload.put("context", context);
        broadcaster.broadcast(payload);

        Map<String, Object> body = new LinkedHashMap<>();
        body.put("status", "processed");
        body.put("decision", decision);
        body.put("developer", context.get("developer"));
        return ResponseEntity.ok(body);
    }

    @GetMapping("/mode")
    public ResponseEntity<Map<String, Object>> mode() {
        return ResponseEntity.ok(Map.of("enabled", mode.isEnabled()));
    }

    @PostMapping("/mode")
    public ResponseEntity<Map<String, Object>> setMode(@RequestBody DeveloperModeRequest request) {
        return ResponseEntity.ok(Map.of("enabled", mode.setEnabled(request.enabled())));
    }

    @GetMapping("/contract")
    public ResponseEntity<Map<String, Object>> contract() {
        return ResponseEntity.ok(Map.of(
                "direction", "core_brain -> connectome -> fly",
                "supported", DeveloperEventMapper.SUPPORTED_TYPES,
                "reserved", DeveloperEventMapper.RESERVED_TYPES,
                "severities", DeveloperEventMapper.KNOWN_SEVERITIES,
                "example", Map.ofEntries(
                        Map.entry("type", "developer.bug_detected"),
                        Map.entry("event_id", "dev_evt_1"),
                        Map.entry("repository", "companion-app"),
                        Map.entry("file", "src/auth/login.ts"),
                        Map.entry("line", 42),
                        Map.entry("column", 10),
                        Map.entry("title", "Possible null reference"),
                        Map.entry("message", "user may be undefined before accessing user.email"),
                        Map.entry("severity", "warning")),
                "version", "v1"));
    }
}
