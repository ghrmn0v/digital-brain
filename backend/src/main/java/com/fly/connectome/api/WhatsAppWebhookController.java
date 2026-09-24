package com.fly.connectome.api;

import java.util.Map;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.fly.connectome.dto.BehaviorDecision;
import com.fly.connectome.dto.EventRequest;
import com.fly.connectome.dto.WhatsAppMessageRequest;
import com.fly.connectome.gateway.BehaviorGateway;
import com.fly.connectome.service.WhatsAppEventMapper;
import com.fly.connectome.ws.FlyBroadcaster;

import jakarta.validation.Valid;

@RestController
@RequestMapping("/api/v1/whatsapp")
public class WhatsAppWebhookController {

    private final WhatsAppEventMapper mapper;
    private final BehaviorGateway gateway;
    private final FlyBroadcaster broadcaster;

    public WhatsAppWebhookController(WhatsAppEventMapper mapper, BehaviorGateway gateway, FlyBroadcaster broadcaster) {
        this.mapper = mapper;
        this.gateway = gateway;
        this.broadcaster = broadcaster;
    }

    @PostMapping("/webhook")
    public ResponseEntity<BehaviorDecision> handleMessage(@Valid @RequestBody WhatsAppMessageRequest message) {
        EventRequest.Normalized event = mapper.map(message);
        BehaviorDecision decision = gateway.decide(event).withBehaviorId("behavior_" + event.id());
        broadcaster.broadcast(Map.of(
                "type", "fly_behavior",
                "behavior_id", decision.behaviorId(),
                "decision", decision,
                "context", event.context()));
        return ResponseEntity.ok(decision);
    }

    @GetMapping("/webhook")
    public ResponseEntity<Map<String, String>> probe() {
        return ResponseEntity.ok(Map.of(
                "status", "active",
                "endpoint", "POST /api/v1/whatsapp/webhook",
                "note", "accepts {sender, senderName, body, type, timestamp}"));
    }
}