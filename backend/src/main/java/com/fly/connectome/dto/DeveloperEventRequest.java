package com.fly.connectome.dto;

import jakarta.validation.constraints.NotBlank;

/**
 * Brain -> Fly developer event (Core Brain provides all text; Fly never generates it).
 * Required fields mirror the agreed contract; eventId/line/column/title are optional
 * so a location can degrade gracefully when Core Brain cannot supply one.
 */
public record DeveloperEventRequest(
        @NotBlank String type,
        String eventId,
        @NotBlank String repository,
        @NotBlank String file,
        Integer line,
        Integer column,
        String title,
        @NotBlank String message,
        @NotBlank String severity) {
}
