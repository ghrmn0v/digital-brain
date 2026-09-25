package com.fly.connectome.service;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.HashSet;
import java.util.Set;

import org.junit.jupiter.api.Test;

class DeveloperLocationMapperTest {

    private final DeveloperLocationMapper mapper = new DeveloperLocationMapper();

    @Test
    void mapsKnownRepositoryAndFileToAStableCodeAnchor() {
        DeveloperLocationMapper.Location first = mapper.map("companion-app", "src/auth/login.ts", 42);
        DeveloperLocationMapper.Location second = mapper.map("companion-app", "src/auth/login.ts", 7);

        assertThat(first.mapped()).isTrue();
        assertThat(DeveloperLocationMapper.CODE_ANCHORS).contains(first.anchor());
        // identical repository/file always land on the same anchor, line does not matter
        assertThat(second.anchor()).isEqualTo(first.anchor());
    }

    @Test
    void differentLocationsSpreadAcrossAnchors() {
        String[][] inputs = {
                {"repo-a", "src/main.ts"},
                {"repo-b", "src/main.ts"},
                {"repo-c", "lib/util.ts"},
                {"repo-d", "test/spec.ts"},
        };
        Set<String> seen = new HashSet<>();
        for (String[] input : inputs) {
            seen.add(mapper.map(input[0], input[1], 1).anchor());
        }
        assertThat(seen).isNotEmpty();
        assertThat(DeveloperLocationMapper.CODE_ANCHORS).containsAll(seen);
    }

    @Test
    void blankRepositoryFallsBackToAttentionArea() {
        DeveloperLocationMapper.Location location = mapper.map(null, "src/a.ts", 1);

        assertThat(location.anchor()).isEqualTo(DeveloperLocationMapper.FALLBACK_ANCHOR);
        assertThat(location.mapped()).isFalse();
    }

    @Test
    void blankFileFallsBackToAttentionArea() {
        DeveloperLocationMapper.Location location = mapper.map("repo", "  ", 1);

        assertThat(location.anchor()).isEqualTo(DeveloperLocationMapper.FALLBACK_ANCHOR);
        assertThat(location.mapped()).isFalse();
    }
}