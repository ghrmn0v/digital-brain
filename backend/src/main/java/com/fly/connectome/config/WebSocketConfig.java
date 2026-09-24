package com.fly.connectome.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.socket.config.annotation.EnableWebSocket;
import org.springframework.web.socket.config.annotation.WebSocketConfigurer;
import org.springframework.web.socket.config.annotation.WebSocketHandlerRegistry;

import com.fly.connectome.ws.FlyBroadcaster;

@Configuration
@EnableWebSocket
public class WebSocketConfig implements WebSocketConfigurer {

    private final FlyBroadcaster broadcaster;

    public WebSocketConfig(FlyBroadcaster broadcaster) {
        this.broadcaster = broadcaster;
    }

    @Override
    public void registerWebSocketHandlers(WebSocketHandlerRegistry registry) {
        registry.addHandler(broadcaster, "/ws/fly")
                .setAllowedOrigins("*");
    }
}