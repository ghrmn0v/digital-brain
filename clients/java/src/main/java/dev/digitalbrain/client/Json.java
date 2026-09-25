package dev.digitalbrain.client;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Minimal, strict JSON reader/writer.
 *
 * <p>The client has no third-party dependencies, so the wire format is handled
 * here with plain JDK types. Values map to {@code Map<String,Object>},
 * {@code List<Object>}, {@code String}, {@code Double}, {@code Boolean} and
 * {@code null}.
 *
 * <p>Serialization is compact and deterministic: object keys are written in
 * insertion order, which for the client means the order the caller built them.
 */
public final class Json {

    private Json() {
    }

    /** Thrown when a payload is not well-formed JSON. */
    public static final class JsonException extends RuntimeException {
        private static final long serialVersionUID = 1L;

        public JsonException(String message) {
            super(message);
        }
    }

    // -- parsing ----------------------------------------------------------------

    public static Object parse(String text) {
        if (text == null) {
            throw new JsonException("json text must not be null");
        }
        Parser parser = new Parser(text);
        Object value = parser.parseValue();
        parser.skipWhitespace();
        if (!parser.atEnd()) {
            throw new JsonException("trailing content at offset " + parser.index());
        }
        return value;
    }

    @SuppressWarnings("unchecked")
    public static Map<String, Object> parseObject(String text) {
        Object value = parse(text);
        if (!(value instanceof Map)) {
            throw new JsonException("expected a json object");
        }
        return (Map<String, Object>) value;
    }

    // -- writing ----------------------------------------------------------------

    public static String write(Object value) {
        StringBuilder out = new StringBuilder();
        writeValue(value, out);
        return out.toString();
    }

    private static void writeValue(Object value, StringBuilder out) {
        if (value == null) {
            out.append("null");
        } else if (value instanceof String) {
            writeString((String) value, out);
        } else if (value instanceof Boolean) {
            out.append(value.toString());
        } else if (value instanceof Double || value instanceof Float) {
            double number = ((Number) value).doubleValue();
            if (Double.isNaN(number) || Double.isInfinite(number)) {
                throw new JsonException("non-finite numbers are not representable");
            }
            if (number == Math.rint(number) && Math.abs(number) < 1e15) {
                out.append((long) number);
            } else {
                out.append(number);
            }
        } else if (value instanceof Number) {
            out.append(value.toString());
        } else if (value instanceof Map) {
            writeObject((Map<?, ?>) value, out);
        } else if (value instanceof Iterable) {
            writeArray((Iterable<?>) value, out);
        } else if (value instanceof Object[]) {
            writeArray(List.of((Object[]) value), out);
        } else {
            throw new JsonException("unsupported json value: " + value.getClass().getName());
        }
    }

    private static void writeObject(Map<?, ?> map, StringBuilder out) {
        out.append('{');
        boolean first = true;
        for (Map.Entry<?, ?> entry : map.entrySet()) {
            if (!first) {
                out.append(',');
            }
            first = false;
            writeString(String.valueOf(entry.getKey()), out);
            out.append(':');
            writeValue(entry.getValue(), out);
        }
        out.append('}');
    }

    private static void writeArray(Iterable<?> items, StringBuilder out) {
        out.append('[');
        boolean first = true;
        for (Object item : items) {
            if (!first) {
                out.append(',');
            }
            first = false;
            writeValue(item, out);
        }
        out.append(']');
    }

    private static void writeString(String value, StringBuilder out) {
        out.append('"');
        for (int index = 0; index < value.length(); index++) {
            char character = value.charAt(index);
            switch (character) {
                case '"':
                    out.append("\\\"");
                    break;
                case '\\':
                    out.append("\\\\");
                    break;
                case '\n':
                    out.append("\\n");
                    break;
                case '\r':
                    out.append("\\r");
                    break;
                case '\t':
                    out.append("\\t");
                    break;
                case '\b':
                    out.append("\\b");
                    break;
                case '\f':
                    out.append("\\f");
                    break;
                default:
                    if (character < 0x20) {
                        out.append(String.format("\\u%04x", (int) character));
                    } else {
                        out.append(character);
                    }
            }
        }
        out.append('"');
    }

    // -- small accessors -------------------------------------------------------

    public static String optString(Map<String, Object> object, String key) {
        Object value = object.get(key);
        return value instanceof String ? (String) value : null;
    }

    @SuppressWarnings("unchecked")
    public static Map<String, Object> optObject(Map<String, Object> object, String key) {
        Object value = object.get(key);
        return value instanceof Map ? (Map<String, Object>) value : null;
    }

    @SuppressWarnings("unchecked")
    public static List<Object> optArray(Map<String, Object> object, String key) {
        Object value = object.get(key);
        return value instanceof List ? (List<Object>) value : Collections.emptyList();
    }

    /** A new mutable object with a stable insertion order. */
    public static Map<String, Object> object() {
        return new LinkedHashMap<>();
    }

    private static final class Parser {
        private final String text;
        private int index;

        Parser(String text) {
            this.text = text;
            this.index = 0;
        }

        int index() {
            return this.index;
        }

        boolean atEnd() {
            return this.index >= this.text.length();
        }

        void skipWhitespace() {
            while (this.index < this.text.length()) {
                char character = this.text.charAt(this.index);
                if (character == ' ' || character == '\t' || character == '\n' || character == '\r') {
                    this.index++;
                } else {
                    break;
                }
            }
        }

        Object parseValue() {
            skipWhitespace();
            if (atEnd()) {
                throw new JsonException("unexpected end of json");
            }
            char character = this.text.charAt(this.index);
            switch (character) {
                case '{':
                    return parseObjectValue();
                case '[':
                    return parseArrayValue();
                case '"':
                    return parseString();
                case 't':
                    expect("true");
                    return Boolean.TRUE;
                case 'f':
                    expect("false");
                    return Boolean.FALSE;
                case 'n':
                    expect("null");
                    return null;
                default:
                    return parseNumber();
            }
        }

        private void expect(String literal) {
            if (!this.text.startsWith(literal, this.index)) {
                throw new JsonException("unexpected token at offset " + this.index);
            }
            this.index += literal.length();
        }

        private Map<String, Object> parseObjectValue() {
            Map<String, Object> object = new LinkedHashMap<>();
            this.index++;
            skipWhitespace();
            if (!atEnd() && this.text.charAt(this.index) == '}') {
                this.index++;
                return object;
            }
            while (true) {
                skipWhitespace();
                if (atEnd() || this.text.charAt(this.index) != '"') {
                    throw new JsonException("expected an object key at offset " + this.index);
                }
                String key = parseString();
                skipWhitespace();
                if (atEnd() || this.text.charAt(this.index) != ':') {
                    throw new JsonException("expected ':' at offset " + this.index);
                }
                this.index++;
                object.put(key, parseValue());
                skipWhitespace();
                if (atEnd()) {
                    throw new JsonException("unterminated object");
                }
                char character = this.text.charAt(this.index);
                if (character == ',') {
                    this.index++;
                    continue;
                }
                if (character == '}') {
                    this.index++;
                    return object;
                }
                throw new JsonException("expected ',' or '}' at offset " + this.index);
            }
        }

        private List<Object> parseArrayValue() {
            List<Object> items = new ArrayList<>();
            this.index++;
            skipWhitespace();
            if (!atEnd() && this.text.charAt(this.index) == ']') {
                this.index++;
                return items;
            }
            while (true) {
                items.add(parseValue());
                skipWhitespace();
                if (atEnd()) {
                    throw new JsonException("unterminated array");
                }
                char character = this.text.charAt(this.index);
                if (character == ',') {
                    this.index++;
                    continue;
                }
                if (character == ']') {
                    this.index++;
                    return items;
                }
                throw new JsonException("expected ',' or ']' at offset " + this.index);
            }
        }

        private String parseString() {
            this.index++;
            StringBuilder out = new StringBuilder();
            while (true) {
                if (atEnd()) {
                    throw new JsonException("unterminated string");
                }
                char character = this.text.charAt(this.index++);
                if (character == '"') {
                    return out.toString();
                }
                if (character != '\\') {
                    out.append(character);
                    continue;
                }
                if (atEnd()) {
                    throw new JsonException("unterminated escape");
                }
                char escaped = this.text.charAt(this.index++);
                switch (escaped) {
                    case '"':
                        out.append('"');
                        break;
                    case '\\':
                        out.append('\\');
                        break;
                    case '/':
                        out.append('/');
                        break;
                    case 'b':
                        out.append('\b');
                        break;
                    case 'f':
                        out.append('\f');
                        break;
                    case 'n':
                        out.append('\n');
                        break;
                    case 'r':
                        out.append('\r');
                        break;
                    case 't':
                        out.append('\t');
                        break;
                    case 'u':
                        if (this.index + 4 > this.text.length()) {
                            throw new JsonException("truncated unicode escape");
                        }
                        String hex = this.text.substring(this.index, this.index + 4);
                        this.index += 4;
                        try {
                            out.append((char) Integer.parseInt(hex, 16));
                        } catch (NumberFormatException exception) {
                            throw new JsonException("invalid unicode escape: " + hex);
                        }
                        break;
                    default:
                        throw new JsonException("invalid escape: \\" + escaped);
                }
            }
        }

        private Double parseNumber() {
            int start = this.index;
            if (!atEnd() && (this.text.charAt(this.index) == '-' || this.text.charAt(this.index) == '+')) {
                this.index++;
            }
            while (!atEnd()) {
                char character = this.text.charAt(this.index);
                if ((character >= '0' && character <= '9')
                        || character == '.'
                        || character == 'e'
                        || character == 'E'
                        || character == '+'
                        || character == '-') {
                    this.index++;
                } else {
                    break;
                }
            }
            String literal = this.text.substring(start, this.index);
            if (literal.isEmpty()) {
                throw new JsonException("expected a value at offset " + start);
            }
            try {
                return Double.valueOf(literal);
            } catch (NumberFormatException exception) {
                throw new JsonException("invalid number: " + literal);
            }
        }
    }
}
