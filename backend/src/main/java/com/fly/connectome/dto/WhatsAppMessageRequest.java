package com.fly.connectome.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

public record WhatsAppMessageRequest(
        String sender,
        String senderName,
        String body,
        @NotBlank String type,
        @NotNull Long timestamp) {
}