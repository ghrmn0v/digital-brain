package com.fly.connectome.gateway;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.concurrent.atomic.AtomicInteger;

import org.junit.jupiter.api.Test;

class RetryerTest {

    private static final class Boom extends RuntimeException {
        Boom() {
            super("boom");
        }
    }

    @Test
    void succeedsOnFirstAttempt() throws Exception {
        String result = Retryer.attempt(() -> "ok", 2);
        assertEquals("ok", result);
    }

    @Test
    void retriesUntilSuccess() throws Exception {
        AtomicInteger calls = new AtomicInteger();
        String result = Retryer.attempt(() -> {
            if (calls.incrementAndGet() < 3) {
                throw new Boom();
            }
            return "recovered";
        }, 3);
        assertEquals(3, calls.get());
        assertEquals("recovered", result);
    }

    @Test
    void givesUpAndPropagatesLastError() {
        AtomicInteger calls = new AtomicInteger();
        Boom thrown = assertThrows(Boom.class, () -> Retryer.attempt(() -> {
            calls.incrementAndGet();
            throw new Boom();
        }, 2));
        assertEquals("boom", thrown.getMessage());
        assertEquals(2, calls.get());
    }

    @Test
    void attemptsAreClampedToAtLeastOne() throws Exception {
        AtomicInteger calls = new AtomicInteger();
        String result = Retryer.attempt(() -> {
            calls.incrementAndGet();
            return "single";
        }, 0);
        assertEquals(1, calls.get());
        assertEquals("single", result);
    }

    @Test
    void backoffGrowsWithAttempt() {
        assertEquals(50L, Retryer.backoffMillis(0));
        assertEquals(150L, Retryer.backoffMillis(2));
        assertTrue(Retryer.backoffMillis(3) > Retryer.backoffMillis(1));
    }
}