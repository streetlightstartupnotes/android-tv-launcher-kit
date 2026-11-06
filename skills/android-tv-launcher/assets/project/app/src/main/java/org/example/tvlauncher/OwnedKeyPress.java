package org.example.tvlauncher;

/** One action for a matching press received by the current, focused UI. */
final class OwnedKeyPress {
    private final boolean vendorMenuRelayEnabled;
    private int key = -1;
    private long downTime = -1;

    OwnedKeyPress() { this(false); }
    OwnedKeyPress(boolean vendorMenuRelayEnabled) {
        this.vendorMenuRelayEnabled = vendorMenuRelayEnabled;
    }

    /**
     * Optional firmware adapter, disabled by default. Some firmware relays MENU
     * as key 82, virtual device -1, flags 30001 (including CANCELED).
     * This is an observed event signature, not an Android-wide guarantee.
     * The Activity must also enforce its resumed + focused ownership boundary.
     */
    boolean acceptMenu(int eventKey, int action, long eventDownTime, int repeat,
            boolean canceled, int flags, int deviceId) {
        boolean vendorRelay = vendorMenuRelayEnabled
                && eventKey == 82 && deviceId == -1 && flags == 30001;
        return accept(eventKey, action, eventDownTime, repeat, canceled && !vendorRelay);
    }

    boolean accept(int eventKey, int action, long eventDownTime, int repeat, boolean canceled) {
        if (canceled) { reset(); return false; }
        if (action == 0) {
            if (repeat == 0) { key = eventKey; downTime = eventDownTime; }
            return false;
        }
        if (action == 1) {
            boolean matched = key == eventKey && downTime >= 0 && downTime == eventDownTime;
            reset();
            return matched;
        }
        reset();
        return false;
    }

    void reset() { key = -1; downTime = -1; }
}
