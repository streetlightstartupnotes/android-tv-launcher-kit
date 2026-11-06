package org.example.tvlauncher.bridge;

/** Vendor startup callbacks may also arrive after standby; only a new boot qualifies. */
final class ColdBootPolicy {
    static final long WINDOW_MS = 180_000L;
    static final long FIRST_FOCUS_WAIT_MS = 8_000L;
    static boolean allows(boolean initialized, int previous, int current, long elapsed) {
        return initialized && previous >= 0 && current > previous
                && elapsed >= 0 && elapsed < WINDOW_MS;
    }
    static boolean withinFirstFocusWindow(long started, long now) {
        return started >= 0 && now >= started && now - started < FIRST_FOCUS_WAIT_MS;
    }
}
