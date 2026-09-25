package com.fly.connectome.dto;

import jakarta.validation.constraints.NotBlank;

public record FeedbackRequest(
        @NotBlank String behaviorId,
        @NotBlank String feedback) {
}