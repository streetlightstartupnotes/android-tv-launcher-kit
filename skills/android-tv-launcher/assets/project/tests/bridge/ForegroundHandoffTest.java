package org.example.tvlauncher.bridge;

public final class ForegroundHandoffTest {
    private static int checks;
    private static void expect(ForegroundHandoff.Decision actual,
            ForegroundHandoff.Decision expected, String label) {
        if (actual != expected) throw new AssertionError(label + ": " + actual);
        checks++;
    }
    public static void main(String[] args) {
        ForegroundHandoff gate = new ForegroundHandoff();
        expect(gate.take(0, 1000, true, true), ForegroundHandoff.Decision.NONE,
                "a lifecycle callback without a HOME request cannot launch");
        long first = gate.request(1000);
        expect(gate.take(first, 1100, false, false), ForegroundHandoff.Decision.WAITING,
                "background HOME creation is passive");
        expect(gate.take(first, 1200, true, false), ForegroundHandoff.Decision.WAITING,
                "resumed without focus cannot replace another page");
        expect(gate.take(first, 1300, false, true), ForegroundHandoff.Decision.WAITING,
                "focus before resume is not enough");
        expect(gate.take(first, 1400, true, true), ForegroundHandoff.Decision.READY,
                "the foreground HOME owner can hand off once");
        expect(gate.take(first, 1401, true, true), ForegroundHandoff.Decision.NONE,
                "duplicate focus/resume callbacks cannot double-start");

        long old = gate.request(2000);
        gate.cancel(); // Paused or lost focus to another source.
        expect(gate.take(old, 2100, true, true), ForegroundHandoff.Decision.NONE,
                "returning focus does not revive canceled work");
        long current = gate.request(3000);
        expect(gate.take(old, 3100, true, true), ForegroundHandoff.Decision.NONE,
                "old callback cannot consume a replacement HOME request");
        expect(gate.take(current, 3200, true, true), ForegroundHandoff.Decision.READY,
                "new explicit request is independent of canceled work");

        old = gate.request(4000);
        expect(gate.take(old, 7000, true, true), ForegroundHandoff.Decision.EXPIRED,
                "late foreground acquisition must not automatically launch");
        expect(gate.take(old, 7001, true, true), ForegroundHandoff.Decision.NONE,
                "expired request cannot retry itself");
        current = gate.request(8000); // Explicit recovery button.
        expect(gate.take(current, 8000, true, true), ForegroundHandoff.Decision.READY,
                "user retry can recover after expiry");

        old = gate.request(9000);
        current = gate.request(11_900);
        expect(gate.take(old, 12_000, true, true), ForegroundHandoff.Decision.NONE,
                "an expired old request cannot invalidate a newer request");
        expect(gate.take(current, 12_001, true, true), ForegroundHandoff.Decision.READY,
                "new request has its own bounded lifetime");
        current = gate.request(13_000);
        expect(gate.take(current, 12_999, true, true), ForegroundHandoff.Decision.EXPIRED,
                "invalid elapsed time cannot authorize a launch");
        System.out.println("ForegroundHandoff: foreground, cancellation, expiry and replacement regressions passed ("
                + checks + " assertions)");
    }
}
