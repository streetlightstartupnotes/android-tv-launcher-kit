package org.example.tvlauncher.bridge;

/** One short-lived HOME handoff, consumable only while the bridge owns focus. */
final class ForegroundHandoff {
    static final long MAX_WAIT_MS = 3_000;
    enum Decision { NONE, WAITING, EXPIRED, READY }

    private long generation;
    private long requestId;
    private long requestedAt;
    private boolean pending;

    long request(long now) {
        requestId = ++generation;
        requestedAt = now;
        pending = true;
        return requestId;
    }

    void cancel() { pending = false; }

    Decision take(long id, long now, boolean resumed, boolean focused) {
        if (!pending || id != requestId) return Decision.NONE;
        if (now < requestedAt || now - requestedAt >= MAX_WAIT_MS) {
            pending = false;
            return Decision.EXPIRED;
        }
        if (!resumed || !focused) return Decision.WAITING;
        pending = false;
        return Decision.READY;
    }
}
