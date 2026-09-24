package com.fly.connectome;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.util.Map;

import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.web.socket.CloseStatus;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fly.connectome.ws.FlyBroadcaster;

class FlyBroadcasterTest {

    private final ObjectMapper mapper = new ObjectMapper();
    private final FlyBroadcaster broadcaster = new FlyBroadcaster(mapper);

    private static WebSocketSession openSession() {
        WebSocketSession session = mock(WebSocketSession.class);
        when(session.isOpen()).thenReturn(true);
        return session;
    }

    @Test
    void broadcastSendsSerializedPayloadToOpenSessions() throws Exception {
        WebSocketSession session = openSession();

        broadcaster.afterConnectionEstablished(session);
        broadcaster.broadcast(Map.of("type", "fly_behavior", "fetch", "IMPORTANT"));

        ArgumentCaptor<TextMessage> captured = ArgumentCaptor.forClass(TextMessage.class);
        verify(session, times(1)).sendMessage(captured.capture());
        Map<String, Object> payload = mapper.readValue(captured.getValue().getPayload(), Map.class);
        assertThat(payload).containsEntry("type", "fly_behavior").containsEntry("fetch", "IMPORTANT");
    }

    @Test
    void broadcastSkipsClosedSessions() throws Exception {
        WebSocketSession open = openSession();
        WebSocketSession closed = mock(WebSocketSession.class);
        when(closed.isOpen()).thenReturn(false);

        broadcaster.afterConnectionEstablished(open);
        broadcaster.afterConnectionEstablished(closed);
        broadcaster.broadcast(Map.of("fetch", "IDLE"));

        verify(open, times(1)).sendMessage(any(TextMessage.class));
        verify(closed, never()).sendMessage(any(TextMessage.class));
    }

    @Test
    void afterConnectionClosedRemovesSession() throws Exception {
        WebSocketSession session = openSession();

        broadcaster.afterConnectionEstablished(session);
        broadcaster.afterConnectionClosed(session, CloseStatus.NORMAL);
        broadcaster.broadcast(Map.of("fetch", "IDLE"));

        verify(session, never()).sendMessage(any(TextMessage.class));
    }

    @Test
    void sendFailureClosesSession() throws Exception {
        WebSocketSession session = openSession();
        org.mockito.Mockito.doThrow(new IllegalStateException("socket closed"))
                .when(session).sendMessage(any(TextMessage.class));

        broadcaster.afterConnectionEstablished(session);
        broadcaster.broadcast(Map.of("fetch", "WARNING"));

        verify(session, times(1)).close(CloseStatus.SERVER_ERROR);
    }
}