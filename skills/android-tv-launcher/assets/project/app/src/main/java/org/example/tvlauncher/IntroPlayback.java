package org.example.tvlauncher;

/** UI commands with a visible-frame clock; no wall-clock timeout runs offscreen. */
final class IntroPlayback {
    static final float DURATION_SECONDS = 6f;
    private volatile int command;
    private int generation;
    private int seenCommand;
    private float seconds = DURATION_SECONDS;
    private boolean pending;

    // Called on the UI thread. Only the most recent command is relevant when
    // the render callback catches up, including cancel -> play in one UI frame.
    void play() { command = ++generation; }
    void cancel() { command = -Math.max(1, generation); }

    // Called on the render callback. A paused or invisible scene passes zero delta.
    // Return a token exactly once, after this intro reaches its final state.
    int advance(float deltaSeconds) {
        int current = command;
        if (current != seenCommand) {
            seenCommand = current;
            pending = current > 0;
            seconds = pending ? 0f : DURATION_SECONDS;
        }
        if (!pending || deltaSeconds <= 0f) return 0;
        seconds = Math.min(DURATION_SECONDS, seconds + deltaSeconds);
        if (seconds < DURATION_SECONDS) return 0;
        pending = false;
        return current;
    }

    float seconds() { return seconds; }
    boolean isCurrent(int token) { return token > 0 && command == token; }
}
