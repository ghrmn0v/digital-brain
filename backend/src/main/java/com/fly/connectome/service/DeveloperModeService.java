package com.fly.connectome.service;

import java.util.concurrent.atomic.AtomicBoolean;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

/**
 * Runtime Developer Mode flag. OFF by default (config-overridable); the product has no
 * pre-existing mode system, so this is the single source of truth for the toggle.
 */
@Service
public class DeveloperModeService {

    private final AtomicBoolean enabled;

    public DeveloperModeService(@Value("${app.developer.enabled:false}") boolean initialEnabled) {
        this.enabled = new AtomicBoolean(initialEnabled);
    }

    public boolean isEnabled() {
        return enabled.get();
    }

    public boolean setEnabled(boolean value) {
        enabled.set(value);
        return enabled.get();
    }
}
