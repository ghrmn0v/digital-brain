package com.fly.connectome.ws;

import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.CloseStatus;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.handler.TextWebSocketHandler;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;

@Component
public class FlyBroadcaster extends TextWebSocketHandler {

    private static final Logger log = LoggerFactory.getLogger(FlyBroadcaster.class);

    private final Set<WebSocketSession> sessions = ConcurrentHashMap.newKeySet();
    private final ObjectMapper mapper;

    public FlyBroadcaster(ObjectMapper mapper) {
        this.mapper = mapper;
    }

    @Override
    public void afterConnectionEstablished(WebSocketSession session) {
        sessions.add(session);
        log.debug("fly client connected: {}", session.getId());
    }

    @Override
    public void afterConnectionClosed(WebSocketSession session, CloseStatus status) {
        sessions.remove(session);
        log.debug("fly client disconnected: {}", session.getId());
    }

    public int clientCount() {
        return sessions.size();
    }

    public void broadcast(Object payload) {
        String message;
        try {
            message = mapper.writeValueAsString(payload);
        } catch (JsonProcessingException exc) {
            log.warn("cannot serialize broadcast payload: {}", exc.getMessage());
            return;
        }
        for (WebSocketSession session : sessions) {
            if (!session.isOpen()) {
                continue;
            }
            try {
                session.sendMessage(new TextMessage(message));
            } catch (Exception exc) {
                log.warn("broadcast to {} failed: {}", session.getId(), exc.getMessage());
                try {
                    session.close(CloseStatus.SERVER_ERROR);
                } catch (Exception ignored) {
                    sessions.remove(session);
                }
            }
        }
    }
}