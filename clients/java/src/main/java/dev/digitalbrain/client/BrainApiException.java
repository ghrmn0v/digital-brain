package dev.digitalbrain.client;

/**
 * A typed failure from the Brain API.
 *
 * <p>{@code code} is the canonical {@code ApiError.code} value (for example
 * {@code validation_error} or {@code unknown_method}). Clients branch on that
 * code, never on an HTTP status.
 */
public final class BrainApiException extends RuntimeException {

    private static final long serialVersionUID = 1L;

    private final String code;
    private final String method;
    private final String requestId;

    public BrainApiException(String code, String message, String method, String requestId) {
        super(message);
        this.code = code;
        this.method = method;
        this.requestId = requestId;
    }

    /** The canonical {@code ApiError.code}, or {@code null} when unknown. */
    public String code() {
        return this.code;
    }

    /** The method that failed, or {@code null} when unknown. */
    public String method() {
        return this.method;
    }

    /** The request id echoed by the Brain, or {@code null}. */
    public String requestId() {
        return this.requestId;
    }

    /** True when the failure is a caller-side input problem. */
    public boolean isValidation() {
        return "validation_error".equals(this.code) || "bad_request".equals(this.code);
    }

    @Override
    public String toString() {
        return "BrainApiException{code=" + this.code
                + ", method=" + this.method
                + ", requestId=" + this.requestId
                + ", message=" + getMessage() + "}";
    }
}
