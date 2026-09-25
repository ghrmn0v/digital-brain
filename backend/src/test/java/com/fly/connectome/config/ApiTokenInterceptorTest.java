package com.fly.connectome.config;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import java.io.PrintWriter;
import java.io.StringWriter;

import org.junit.jupiter.api.Test;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

class ApiTokenInterceptorTest {

    private final StringWriter body = new StringWriter();

    private HttpServletResponse response() throws Exception {
        HttpServletResponse response = mock(HttpServletResponse.class);
        PrintWriter writer = new PrintWriter(body, true);
        when(response.getWriter()).thenReturn(writer);
        return response;
    }

    @Test
    void emptyTokenDisablesAuthentication() throws Exception {
        ApiTokenInterceptor interceptor = new ApiTokenInterceptor(null);
        HttpServletResponse response = response();

        boolean allowed = interceptor.preHandle(mock(HttpServletRequest.class), response, null);

        assert allowed;
        verifyNoInteractions(response);
    }

    @Test
    void wrongOrMissingTokenIsRejectedOnPost() throws Exception {
        ApiTokenInterceptor interceptor = new ApiTokenInterceptor("top-secret");
        HttpServletRequest request = mock(HttpServletRequest.class);
        when(request.getMethod()).thenReturn("POST");
        when(request.getHeader("X-Fly-Token")).thenReturn("guess");

        boolean missing = interceptor.preHandle(request, response(), null);
        assert !missing;

        HttpServletResponse rejected = response();
        boolean wrong = interceptor.preHandle(request, rejected, null);
        assert !wrong;
        verify(rejected).setStatus(HttpServletResponse.SC_UNAUTHORIZED);
    }

    @Test
    void matchingTokenIsAllowed() throws Exception {
        ApiTokenInterceptor interceptor = new ApiTokenInterceptor(" top-secret ");
        HttpServletRequest request = mock(HttpServletRequest.class);
        when(request.getMethod()).thenReturn("POST");
        when(request.getHeader("X-Fly-Token")).thenReturn("top-secret");

        assert interceptor.preHandle(request, response(), null);
    }

    @Test
    void readsAreNeverRejected() throws Exception {
        ApiTokenInterceptor interceptor = new ApiTokenInterceptor("top-secret");
        HttpServletRequest request = mock(HttpServletRequest.class);
        when(request.getMethod()).thenReturn("GET");

        assert interceptor.preHandle(request, response(), null);
    }
}