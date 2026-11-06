package org.example.tvlauncher;

import android.content.Context;
import android.view.Gravity;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;

/** Local presentation preferences and explicit links to Android settings. */
final class SettingsPanel extends FrameLayout {
    private final MainActivity host;
    private final LinearLayout rows;
    private boolean showingAbout;

    SettingsPanel(MainActivity activity) {
        super(activity);
        host = activity;
        setBackgroundColor(0xe8080f15);
        host.addPageHeader(this, "Settings", "");
        rows = new LinearLayout(host);
        rows.setOrientation(LinearLayout.VERTICAL);
        FrameLayout.LayoutParams layout = new FrameLayout.LayoutParams(host.dp(500), -2);
        layout.leftMargin = host.dp(56); layout.topMargin = host.dp(105);
        addView(rows, layout);
        buildRows();
    }

    private void buildRows() {
        showingAbout = false;
        rows.removeAllViews();
        row("Network", "Open system settings", () -> NativeEntries.openAction(host, R.string.native_wifi_action));
        row("Bluetooth and remotes", "Open system settings", () -> NativeEntries.openAction(host, R.string.native_bluetooth_action));
        final TextView[] timeout = new TextView[1];
        timeout[0] = row("Home idle saver", idleLabel(), () -> {
            int[] times = {0, 60, 120, 300, 600};
            int current = host.idleSeconds(), next = 0;
            for (int i = 0; i < times.length; i++) if (times[i] == current) next = (i + 1) % times.length;
            host.getSharedPreferences("display", Context.MODE_PRIVATE).edit().putInt("idleSeconds", times[next]).apply();
            timeout[0].setText(idleLabel());
            host.armIdle();
        });
        row("Screen saver", "Start now", () -> host.setSaver(true));
        row("Display", "Open system settings", () -> NativeEntries.openAction(host, R.string.native_display_action));
        row("System settings", "Open", () -> NativeEntries.openMenu(host));
        row("About Quiet TV", "1.0.0", this::about);
        rows.getChildAt(0).requestFocus();
    }

    boolean handleBack() {
        if (!showingAbout) return false;
        buildRows();
        rows.getChildAt(rows.getChildCount() - 1).requestFocus();
        return true;
    }
    private String idleLabel() {
        int seconds = host.idleSeconds();
        return seconds == 0 ? "Off (manual only)" : seconds / 60 + " minutes";
    }
    private TextView row(String title, String value, Runnable action) {
        LinearLayout line = new LinearLayout(host);
        line.setGravity(Gravity.CENTER_VERTICAL);
        line.setPadding(host.dp(15), 0, host.dp(15), 0);
        line.setFocusable(action != null); line.setClickable(action != null);
        TextView label = host.text(title, 17, 0xffd0e0de);
        TextView detail = host.text(value, 12, 0xff799da4);
        detail.setGravity(Gravity.RIGHT | Gravity.CENTER_VERTICAL);
        line.addView(label, new LinearLayout.LayoutParams(0, -2, 1));
        line.addView(detail, new LinearLayout.LayoutParams(-2, -2));
        LinearLayout.LayoutParams layout = new LinearLayout.LayoutParams(-1, host.dp(45));
        layout.bottomMargin = host.dp(5); rows.addView(line, layout);
        line.setOnFocusChangeListener((view, focused) -> {
            line.setBackground(host.focusSurface(focused, 7));
            label.setTextColor(focused ? MainActivity.WHITE : 0xffb6cbc9);
        });
        if (action != null) line.setOnClickListener(view -> action.run());
        return detail;
    }
    private void about() {
        showingAbout = true; rows.removeAllViews();
        row("Quiet TV", "Example project", null);
        row("Animation", "Inside the application only", null);
        row("Screen saver", "Manual by default", null);
        row("Back to settings", "Back", this::handleBack);
        rows.getChildAt(rows.getChildCount() - 1).requestFocus();
    }
}
