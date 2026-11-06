package org.example.tvlauncher.bridge;

/** Pure boot policy. elapsedRealtime includes standby, unlike uptimeMillis. */
final class BootDecision {
    static final long BOOT_WINDOW_MS = 10L * 60L * 1000L;

    private BootDecision() { }

    static boolean showBootScene(boolean initialized, int previousBoot,
            int currentBoot, long elapsedRealtimeMs) {
        // A first installation or unavailable/reset counter only establishes a baseline.
        return initialized && previousBoot >= 0 && currentBoot > previousBoot
                && elapsedRealtimeMs >= 0 && elapsedRealtimeMs < BOOT_WINDOW_MS;
    }
}
