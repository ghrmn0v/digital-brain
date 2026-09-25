package com.fly.connectome.service;

import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;

import org.springframework.stereotype.Service;

import com.fly.connectome.dto.EventRequest;
import com.fly.connectome.dto.WhatsAppMessageRequest;

@Service
public class WhatsAppEventMapper {

    private static final int BODY_PREVIEW = 80;
    private static final String SOURCE = "whatsapp";

    public EventRequest.Normalized map(WhatsAppMessageRequest message) {
        String type = normalizeType(message.type());
        return new EventRequest.Normalized(
                UUID.randomUUID().toString(),
                eventName(type),
                SOURCE,
                priority(type),
                context(message, type),
                null);
    }

    static String normalizeType(String type) {
        if (type == null) {
            return "chat";
        }
        String lower = type.toLowerCase(Locale.ROOT);
        return switch (lower) {
            case "ptt", "audio", "voice" -> "audio";
            case "image", "photo" -> "image";
            case "video", "gif" -> "video";
            case "sticker" -> "sticker";
            default -> "text";
        };
    }

    static String eventName(String type) {
        return switch (type) {
            case "audio", "image", "video", "sticker" -> "notification";
            default -> "user_message";
        };
    }

    static double priority(String type) {
        return switch (type) {
            case "audio" -> 0.85;
            case "image", "video" -> 0.75;
            case "sticker" -> 0.6;
            default -> 0.4;
        };
    }

    static Map<String, Object> context(WhatsAppMessageRequest message, String type) {
        Map<String, Object> context = new LinkedHashMap<>();
        context.put("sender", message.sender() == null ? "unknown" : message.sender());
        context.put("sender_name", message.senderName() == null ? "unknown" : message.senderName());
        context.put("media_type", type);
        context.put("body_preview", preview(message.body()));
        return Map.copyOf(context);
    }

    static String preview(String body) {
        if (body == null) {
            return "";
        }
        String flat = body.replaceAll("\\s+", " ").trim();
        if (flat.length() <= BODY_PREVIEW) {
            return flat;
        }
        return flat.substring(0, BODY_PREVIEW) + "\u2026";
    }
}