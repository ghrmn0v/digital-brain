package com.fly.connectome.service;

import java.util.List;
import java.util.Objects;

import org.springframework.stereotype.Service;

/**
 * Maps a Core Brain code location (repository/file/line) to a Fly visual anchor.
 * The Fly has no code-editor surface yet, so locations are mapped deterministically
 * onto a small set of on-screen anchors; unknown input falls back to the attention area.
 */
@Service
public class DeveloperLocationMapper {

    public static final List<String> CODE_ANCHORS = List.of("code_1", "code_2", "code_3", "code_4");
    public static final String FALLBACK_ANCHOR = "attention_area";

    public record Location(String anchor, boolean mapped) {
    }

    public Location map(String repository, String file, Integer line) {
        if (isBlank(repository) || isBlank(file)) {
            return new Location(FALLBACK_ANCHOR, false);
        }
        int slot = Math.floorMod(Objects.hash(repository, file), CODE_ANCHORS.size());
        return new Location(CODE_ANCHORS.get(slot), true);
    }

    private static boolean isBlank(String value) {
        return value == null || value.isBlank();
    }
}
