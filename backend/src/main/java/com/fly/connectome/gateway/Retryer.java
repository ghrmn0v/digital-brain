package com.fly.connectome.gateway;

/**
 * Small retry helper used at the service boundary so transient Python/network
 * hiccups do not instantly degrade a decision to the fallback policy.
 */
public final class Retryer {

    @FunctionalInterface
    public interface Body<T> {
        T run() throws Exception;
    }

    private Retryer() {
    }

    public static <T> T attempt(Body<T> body, int attempts) throws Exception {
        int n = Math.max(1, attempts);
        Exception last = null;
        for (int i = 0; i < n; i++) {
            try {
                return body.run();
            } catch (Exception exc) {
                last = exc;
                if (i < n - 1) {
                    Thread.sleep(backoffMillis(i));
                }
            }
        }
        if (last == null) {
            throw new IllegalStateException("no attempts configured");
        }
        throw last;
    }

    static long backoffMillis(int attempt) {
        return 50L * (attempt + 1);
    }
}