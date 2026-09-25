package com.fly.connectome.service;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Map;

import org.junit.jupiter.api.Test;

import com.fly.connectome.dto.EventRequest;
import com.fly.connectome.dto.WhatsAppMessageRequest;

class WhatsAppEventMapperTest {

    private final WhatsAppEventMapper mapper = new WhatsAppEventMapper();

    private static WhatsAppMessageRequest message(String type, String body) {
        return new WhatsAppMessageRequest("+994501112233", "Sado", body, type, 1758700000L);
    }

    @Test
    void mapsImageToNotificationWithHighPriority() {
        EventRequest.Normalized event = mapper.map(message("image", "şəkil"));

        assertThat(event.name()).isEqualTo("notification");
        assertThat(event.source()).isEqualTo("whatsapp");
        assertThat(event.priority()).isEqualTo(0.75);
    }

    @Test
    void mapsTextToUserMessage() {
        EventRequest.Normalized event = mapper.map(message("chat", "salam"));

        assertThat(event.name()).isEqualTo("user_message");
        assertThat(event.priority()).isEqualTo(0.4);
    }

    @Test
    void mapsVoiceNoteToAudioPriority() {
        assertThat(mapper.map(message("ptt", "səs")).priority()).isEqualTo(0.85);
        assertThat(mapper.map(message("audio", "səs")).priority()).isEqualTo(0.85);
        assertThat(mapper.map(message("ptt", "səs")).name()).isEqualTo("notification");
    }

    @Test
    void contextCarriesSenderAndMediaType() {
        Map<String, Object> context = mapper.map(message("sticker", "st")).context();

        assertThat(context.get("sender")).isEqualTo("+994501112233");
        assertThat(context.get("sender_name")).isEqualTo("Sado");
        assertThat(context.get("media_type")).isEqualTo("sticker");
    }

    @Test
    void longBodyIsTruncatedToPreview() {
        String longBody = "a".repeat(500);
        Map<String, Object> context = mapper.map(message("chat", longBody)).context();

        assertThat((String) context.get("body_preview")).hasSize(81).endsWith("\u2026");
    }

    @Test
    void previewCollapsesWhitespace() {
        assertThat(WhatsAppEventMapper.preview("  \n 你好 \n world  ")).isEqualTo("你好 world");
    }

    @Test
    void mediaMessageWithNullBodyIsHandled() {
        EventRequest.Normalized event = mapper.map(
                new WhatsAppMessageRequest("+994501112233", "Sado", null, "image", 1758700000L));

        assertThat((String) event.context().get("body_preview")).isEmpty();
        assertThat(event.priority()).isEqualTo(0.75);
    }

    @Test
    void normalizesUnknownTypeToText() {
        assertThat(WhatsAppEventMapper.normalizeType("weird")).isEqualTo("text");
        assertThat(WhatsAppEventMapper.normalizeType(null)).isEqualTo("chat");
        assertThat(WhatsAppEventMapper.eventName("chat")).isEqualTo("user_message");
    }
}