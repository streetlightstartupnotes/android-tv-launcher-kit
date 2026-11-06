package org.example.tvlauncher.bridge;

import android.app.Activity;
import android.content.ComponentName;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.os.SystemClock;
import android.provider.Settings;
import android.util.Log;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

/** A single-purpose HOME handoff. It does not manage firmware or boot animation. */
public final class BridgeActivity extends Activity {
    private static final String TAG = "QuietTvBridge";
    private static final String PREFS = "bridge_state";
    private static final String INITIALIZED = "initialized";
    private static final String LAST_BOOT = "last_boot_count";
    private static final String FAILED = "forward_failure_latched";

    private boolean failed;
    private boolean recoveryVisible;
    private OwnedKeyPress menuPress;
    private boolean resumed;
    private boolean focused;
    private final ForegroundHandoff handoff = new ForegroundHandoff();
    private long handoffId;

    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        menuPress = new OwnedKeyPress(getResources().getBoolean(R.bool.enable_vendor_menu_relay));
        // Creating HOME in a background task is not permission to replace the
        // active source. Defer the one handoff until this Activity owns focus.
        requestHandoff();
    }

    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        menuPress.reset();
        requestHandoff(); // Replaces any previous request; old callbacks cannot consume it.
    }

    private void requestHandoff() {
        handoff.cancel();
        handoffId = handoff.request(SystemClock.uptimeMillis());
        forwardIfForeground();
    }

    private void forwardIfForeground() {
        if (isFinishing()) return;
        boolean foreground = resumed && focused && hasWindowFocus();
        ForegroundHandoff.Decision decision = handoff.take(handoffId,
                SystemClock.uptimeMillis(), resumed, focused && hasWindowFocus());
        if (decision == ForegroundHandoff.Decision.READY) forwardHome();
        else if (foreground && decision != ForegroundHandoff.Decision.WAITING) {
            // A canceled/expired request is never revived on a later resume.
            // If HOME is now visible, offer an explicit retry instead of a blank.
            failed = true;
            showRecovery();
        }
    }

    private void forwardHome() {
        if (isFinishing() || !resumed || !focused || !hasWindowFocus()) return;
        try {
            SharedPreferences state = getSharedPreferences(PREFS, MODE_PRIVATE);
            if (failed || state.getBoolean(FAILED, false)) {
                failed = true;
                Log.e(TAG, "forward_blocked: waiting for user retry");
                showRecovery();
                return;
            }

            int bootCount = readBootCount();
            int previousBoot = state.getInt(LAST_BOOT, -1);
            boolean initialized = state.getBoolean(INITIALIZED, false);
            long elapsedMs = SystemClock.elapsedRealtime();
            boolean bootScene = BootDecision.showBootScene(
                    initialized, previousBoot, bootCount, elapsedMs);

            // Commit before handoff so a second HOME launch cannot repeat the boot scene.
            SharedPreferences.Editor update = state.edit().putBoolean(INITIALIZED, true);
            if (bootCount >= 0) update.putInt(LAST_BOOT, bootCount);
            if (!update.commit()) {
                bootScene = false;
                Log.w(TAG, "state_commit_failed: suppressing boot scene");
            }

            Intent home = new Intent(Intent.ACTION_MAIN).setComponent(target())
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP
                            | Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_NO_ANIMATION)
                    .putExtra(bootScene ? "boot_scene" : "home_key", true);
            // Do not forward caller-supplied extras, data, categories, or flags.
            startActivity(home);
            finish();
            overridePendingTransition(0, 0);
        } catch (RuntimeException error) {
            stopAfterFailure(error);
        }
    }

    private int readBootCount() {
        try {
            return Settings.Global.getInt(getContentResolver(), "boot_count", -1);
        } catch (RuntimeException error) {
            Log.w(TAG, "boot_count_unavailable: suppressing boot scene", error);
            return -1;
        }
    }

    private void stopAfterFailure(RuntimeException error) {
        failed = true;
        try {
            if (!getSharedPreferences(PREFS, MODE_PRIVATE).edit().putBoolean(FAILED, true).commit()) {
                Log.e(TAG, "failure_latch_not_persisted: this Activity still stops retries");
            }
        } catch (RuntimeException storageError) {
            Log.e(TAG, "failure_latch_storage_error: this Activity still stops retries", storageError);
        }
        Log.e(TAG, "Handoff failed; waiting for an explicit retry", error);
        showRecovery();
        // Do not finish: Android might immediately recreate its missing HOME otherwise.
    }

    private void retryFromUser() {
        if (!resumed || !focused || !hasWindowFocus()) return;
        try {
            // Keep the boot baseline: retrying cannot consume the same opening
            // again, and never requires clearing either application's data.
            if (!getSharedPreferences(PREFS, MODE_PRIVATE).edit().remove(FAILED).commit()) {
                Toast.makeText(this, "Unable to retry right now", Toast.LENGTH_LONG).show();
                return;
            }
            failed = false;
            requestHandoff();
        } catch (RuntimeException error) {
            stopAfterFailure(error);
        }
    }

    private void showRecovery() {
        if (recoveryVisible) return;
        recoveryVisible = true;
        getWindow().getDecorView().setSystemUiVisibility(5894);
        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setGravity(Gravity.CENTER);
        content.setPadding(dp(48), dp(32), dp(48), dp(32));
        content.setBackgroundColor(Color.rgb(8, 13, 17));

        TextView title = new TextView(this);
        title.setText("Quiet TV is temporarily unavailable");
        title.setTextColor(Color.rgb(244, 245, 237));
        title.setTextSize(27);
        title.setGravity(Gravity.CENTER);
        title.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        content.addView(title, new LinearLayout.LayoutParams(-1, -2));

        LinearLayout actions = new LinearLayout(this);
        actions.setOrientation(LinearLayout.HORIZONTAL);
        actions.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams row = new LinearLayout.LayoutParams(-1, -2);
        row.topMargin = dp(32);
        content.addView(actions, row);

        TextView retry = recoveryButton("Try again", this::retryFromUser);
        TextView settings = recoveryButton("System settings", this::openSettings);
        for (TextView button : new TextView[]{retry, settings}) {
            LinearLayout.LayoutParams size = new LinearLayout.LayoutParams(dp(220), dp(56));
            size.setMargins(dp(8), 0, dp(8), 0);
            actions.addView(button, size);
        }
        retry.setNextFocusRightId(settings.getId());
        settings.setNextFocusLeftId(retry.getId());
        setContentView(content);
        retry.requestFocus();
    }

    private TextView recoveryButton(String label, Runnable action) {
        TextView button = new TextView(this);
        button.setId(View.generateViewId());
        button.setText(label);
        button.setTextSize(18);
        button.setTextColor(Color.rgb(244, 245, 237));
        button.setGravity(Gravity.CENTER);
        button.setFocusable(true);
        button.setClickable(true);
        button.setOnClickListener(view -> action.run());
        button.setOnFocusChangeListener((view, focused) -> styleButton(button, focused));
        styleButton(button, false);
        return button;
    }

    private void styleButton(TextView button, boolean focused) {
        GradientDrawable background = new GradientDrawable();
        background.setColor(focused ? Color.rgb(39, 66, 73) : Color.rgb(19, 30, 36));
        background.setCornerRadius(dp(8));
        background.setStroke(dp(1), focused ? Color.rgb(202, 235, 237) : Color.rgb(53, 70, 77));
        button.setBackground(background);
    }

    private ComponentName target() {
        String targetPackage = getString(R.string.target_package);
        if (targetPackage.isEmpty() || targetPackage.equals(getPackageName()))
            throw new IllegalStateException("Bridge target must be a separate application");
        return new ComponentName(targetPackage, getString(R.string.target_activity));
    }

    private void openSettings() {
        if (!resumed || !focused || !hasWindowFocus()) return;
        try {
            startActivity(new Intent(Settings.ACTION_SETTINGS));
        } catch (RuntimeException error) {
            Toast.makeText(this, "System settings are unavailable", Toast.LENGTH_LONG).show();
        }
    }

    private int dp(float value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    @Override public boolean dispatchKeyEvent(KeyEvent event) {
        if (!resumed || !focused || !hasWindowFocus()) {
            menuPress.reset();
            return super.dispatchKeyEvent(event);
        }
        if (event.getKeyCode() != KeyEvent.KEYCODE_MENU && event.getAction() == KeyEvent.ACTION_DOWN)
            menuPress.reset();
        if (!failed || event.getKeyCode() != KeyEvent.KEYCODE_MENU) {
            return super.dispatchKeyEvent(event);
        }
        if (menuPress.acceptMenu(event.getKeyCode(), event.getAction(), event.getDownTime(),
                event.getRepeatCount(), event.isCanceled(), event.getFlags(), event.getDeviceId())) openSettings();
        return true;
    }

    @Override public void onWindowFocusChanged(boolean focused) {
        super.onWindowFocusChanged(focused);
        boolean lostFocus = this.focused && !focused;
        this.focused = focused;
        if (lostFocus) handoff.cancel();
        if (!focused) menuPress.reset();
        else forwardIfForeground();
    }

    @Override protected void onResume() {
        super.onResume();
        resumed = true;
        focused = hasWindowFocus();
        forwardIfForeground();
    }

    @Override protected void onPause() {
        resumed = false;
        focused = false;
        handoff.cancel();
        menuPress.reset();
        super.onPause();
    }

    @Override public void onBackPressed() {
        handoff.cancel();
        // HOME's failure holding state must not finish and cause a relaunch loop.
        if (!failed) super.onBackPressed();
    }
}
