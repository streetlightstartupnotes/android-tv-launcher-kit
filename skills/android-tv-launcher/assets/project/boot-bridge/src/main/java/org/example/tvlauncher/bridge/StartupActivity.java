package org.example.tvlauncher.bridge;
import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.os.Handler;
import android.os.SystemClock;
import android.provider.Settings;
import android.util.Log;

/** A one-shot cold-boot handoff from the explicitly configured vendor INFO entry.
 * Standby, ordinary HOME, package updates and late callbacks never launch Main. */
public final class StartupActivity extends Activity {
    private final Handler handler = new Handler(android.os.Looper.getMainLooper());
    private final Runnable expire = () -> {
        Log.i("QuietTvStartup", "first-focus wait expired; no launch");
        eligible = false; finish();
    };
    private boolean eligible, resumed, sent, hadFocus;
    private long focusWaitStarted;
    private static int boot(Context context) {
        try { return Settings.Global.getInt(context.getContentResolver(), "boot_count", -1); }
        catch (RuntimeException unavailable) { return -1; }
    }
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        SharedPreferences p = getSharedPreferences("bridge_state", MODE_PRIVATE);
        int current = boot(this), previous = p.getInt("last_boot_count", -1);
        eligible = ColdBootPolicy.allows(p.getBoolean("initialized", false), previous, current,
                SystemClock.elapsedRealtime());
        // Consume even an expired or interrupted callback: never retry later over another app.
        if (current >= 0 && !p.edit().putBoolean("initialized", true).putInt("last_boot_count", current).commit()) eligible = false;
        if (!eligible) { finish(); return; }
        getWindow().getDecorView().setSystemUiVisibility(5894);
        focusWaitStarted = SystemClock.elapsedRealtime();
        handler.postDelayed(expire, ColdBootPolicy.FIRST_FOCUS_WAIT_MS);
    }
    private android.content.ComponentName target() {
        String targetPackage = getString(R.string.target_package);
        if (targetPackage.isEmpty() || targetPackage.equals(getPackageName()))
            throw new IllegalStateException("Startup target must be a separate application");
        return new android.content.ComponentName(targetPackage, getString(R.string.target_activity));
    }
    private void forward() {
        if (!eligible || sent || !resumed || !hasWindowFocus() || isFinishing()) return;
        // Handler dispatch can be delayed; real elapsed time still bounds the handoff.
        if (!ColdBootPolicy.withinFirstFocusWindow(focusWaitStarted, SystemClock.elapsedRealtime())) {
            eligible = false; handler.removeCallbacks(expire); finish(); return;
        }
        sent = true; eligible = false; handler.removeCallbacks(expire);
        try {
            startActivity(new Intent(Intent.ACTION_MAIN).setComponent(target())
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_CLEAR_TOP|Intent.FLAG_ACTIVITY_SINGLE_TOP)
                    .putExtra("boot_scene", true));
            Log.i("QuietTvStartup", "foreground cold boot forwarded once");
        } catch (RuntimeException error) { Log.w("QuietTvStartup", "handoff failed; no retry", error); }
        finish();
        overridePendingTransition(0, 0);
    }
    @Override protected void onResume() {
        super.onResume(); resumed = true;
        forward();
    }
    @Override public void onWindowFocusChanged(boolean focused) {
        super.onWindowFocusChanged(focused);
        if (focused) { hadFocus = true; forward(); }
        else if (resumed && hadFocus) { eligible = false; finish(); }
    }
    @Override protected void onPause() {
        resumed = false; eligible = false; handler.removeCallbacks(expire);
        Log.i("QuietTvStartup", "startup paused; pending request canceled");
        super.onPause(); finish();
    }
    @Override protected void onDestroy() {
        handler.removeCallbacks(expire); super.onDestroy();
    }
}
