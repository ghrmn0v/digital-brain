package com.fly.connectome.config;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import org.springframework.web.servlet.HandlerInterceptor;

/**
 * Shared-secret boundary for write endpoints. Configured via the environment
 * (never committed): FLY_API_TOKEN / app.security.api-token. An empty token means
 * authentication is disabled (local development default); when set, only requests
 * carrying the matching X-Fly-Token header are allowed past the interception paths.
 */
public class ApiTokenInterceptor implements HandlerInterceptor {

    private final String token;

    public ApiTokenInterceptor(String token) {
        this.token = token == null ? "" : token.trim();
    }

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler)
            throws Exception {
        if (token.isEmpty()) {
            return true;
        }
        if (!"POST".equalsIgnoreCase(request.getMethod())) {
            return true;
        }
        String supplied = request.getHeader("X-Fly-Token");
        if (token.equals(supplied)) {
            return true;
        }
        response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
        response.setContentType("application/json");
        response.getWriter().write("{\"code\":\"unauthorized\"}");
        return false;
    }
}