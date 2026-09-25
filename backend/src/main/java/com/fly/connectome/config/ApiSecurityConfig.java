package com.fly.connectome.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * Protects the write API surface (Brain events, feedback, WhatsApp ingestion,
 * developer events/mode) behind the env-configured shared token. Spring Boot is
 * the service boundary: external callers authenticate here, never against
 * internal components.
 */
@Configuration
public class ApiSecurityConfig implements WebMvcConfigurer {

    private final ApiTokenInterceptor interceptor;

    public ApiSecurityConfig(@Value("${app.security.api-token:}") String token) {
        this.interceptor = new ApiTokenInterceptor(token);
    }

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(interceptor)
                .addPathPatterns(
                        "/api/v1/events",
                        "/api/v1/feedback",
                        "/api/v1/whatsapp/webhook",
                        "/api/v1/developer/events",
                        "/api/v1/developer/mode");
    }
}