package org.example.tvlauncher;

public final class IntroPlaybackTest {
    private static void check(boolean value, String message) {
        if (!value) throw new AssertionError(message);
    }
    public static void main(String[] args) {
        IntroPlayback clock = new IntroPlayback();
        check(clock.advance(1f) == 0, "ordinary home must not complete an intro");
        clock.play();
        check(clock.advance(2f) == 0 && clock.seconds() == 2f, "first visible segment");
        for (int i = 0; i < 100; i++) check(clock.advance(0f) == 0, "paused intro fired");
        check(clock.seconds() == 2f, "focus loss advanced the intro");
        // Surface/context recreation preserves this clock, while the caller
        // resets the previous frame timestamp; its first resumed delta is zero.
        check(clock.advance(0f) == 0 && clock.seconds() == 2f, "surface recreation reset progress");
        int first = clock.advance(4f);
        check(first > 0 && clock.isCurrent(first), "completion token missing");
        check(clock.advance(1f) == 0, "completion repeated");
        clock.cancel();
        check(!clock.isCurrent(first), "cancel allowed a queued callback");
        check(clock.advance(0f) == 0 && clock.seconds() == 6f, "cancel did not settle");
        clock.play();
        clock.cancel();
        clock.play();
        check(clock.advance(0f) == 0 && clock.seconds() == 0f,
                "an earlier cancel swallowed the next intro before the render frame");
        int last = clock.advance(6f);
        check(last > first && clock.isCurrent(last), "replacement intro did not complete");
        clock.play();
        check(!clock.isCurrent(last), "new intro allowed an old queued callback");
        clock.advance(1f);
        clock.cancel();
        check(clock.advance(6f) == 0, "canceled intro completed");
        System.out.println("IntroPlayback lifecycle cases passed");
    }
}
