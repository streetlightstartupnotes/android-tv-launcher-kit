package org.example.tvlauncher.bridge;

public final class BootDecisionTest {
    private static int cases;

    private static void check(boolean expected, boolean initialized, int previous,
            int current, long elapsed, String label) {
        boolean actual = BootDecision.showBootScene(initialized, previous, current, elapsed);
        if (actual != expected) throw new AssertionError(label + ": " + actual);
        cases++;
    }

    public static void main(String[] args) {
        check(false, false, -1, 100, 5_000, "first install early after boot");
        check(false, false, -1, 100, 900_000, "first install late after boot");
        check(false, true, 100, 100, 5_000, "second HOME in same boot");
        check(true, true, 100, 101, 5_000, "first HOME in next boot");
        check(false, true, 101, 101, 6_000, "boot scene consumed before second HOME");
        check(true, true, 100, 102, 599_999, "skipped boot still detected");
        check(false, true, 100, 101, 600_000, "ten minute boundary");
        check(false, true, 100, 101, 86_400_000, "standby does not restart window");
        check(false, true, -1, 101, 5_000, "missing previous count only baselines");
        check(false, true, 100, -1, 5_000, "current count unavailable");
        check(false, true, 100, 0, 5_000, "counter reset only baselines");
        check(false, true, 100, 101, -1, "invalid elapsed time");
        System.out.println("BootDecision: " + cases + " cases passed");
    }
}
