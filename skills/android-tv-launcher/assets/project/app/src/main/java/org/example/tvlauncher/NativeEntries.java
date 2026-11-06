package org.example.tvlauncher;

import android.app.Activity;
import android.content.ComponentName;
import android.content.Intent;
import android.widget.Toast;

/** Explicit links only: no settings writes, global key hooks or background starts. */
final class NativeEntries {
    private NativeEntries() { }

    static void openMenu(Activity host) {
        openConfigured(host, host.getString(R.string.native_menu_mode),
                host.getString(R.string.native_menu_action), host.getString(R.string.native_menu_component));
    }
    static void openInputs(Activity host) {
        openConfigured(host, host.getString(R.string.native_inputs_mode),
                host.getString(R.string.native_inputs_action), host.getString(R.string.native_inputs_component));
    }
    static void openAction(Activity host, int actionResource) {
        openConfigured(host, "activity", host.getString(actionResource), "");
    }
    static void openOriginalHome(Activity host) {
        openConfigured(host, "activity", Intent.ACTION_MAIN,
                host.getString(R.string.native_original_home_component));
    }
    static boolean hasOriginalHome(Activity host) {
        return originalHomeComponent(host) != null;
    }
    static String originalHomePackage(Activity host) {
        ComponentName component = originalHomeComponent(host);
        return component == null ? "" : component.getPackageName();
    }
    private static ComponentName originalHomeComponent(Activity host) {
        return ComponentName.unflattenFromString(host.getString(R.string.native_original_home_component));
    }

    private static void openConfigured(Activity host, String mode, String action, String flattened) {
        if (host.isFinishing() || !host.hasWindowFocus()) return;
        // Original home must be explicit: ACTION_MAIN without a component is not a fallback.
        if ((action.isEmpty() && flattened.isEmpty())
                || (Intent.ACTION_MAIN.equals(action) && flattened.isEmpty())) {
            unavailable(host); return;
        }
        Intent intent = new Intent(action.isEmpty() ? null : action);
        if (!flattened.isEmpty()) {
            ComponentName component = ComponentName.unflattenFromString(flattened);
            if (component == null || component.getPackageName().equals(host.getPackageName())
                    || component.getPackageName().equals("org.example.tvlauncher.bridge")) {
                unavailable(host); return;
            }
            intent.setComponent(component);
        }
        try {
            if ("broadcast".equals(mode)) {
                // Adapted firmware broadcasts must target one verified exported receiver.
                if (intent.getComponent() == null
                        || host.getPackageManager().queryBroadcastReceivers(intent, 0).isEmpty()) {
                    unavailable(host); return;
                }
                host.sendBroadcast(intent);
            } else if ("activity".equals(mode)) {
                host.startActivity(intent);
            } else {
                unavailable(host);
            }
        } catch (RuntimeException unavailable) {
            unavailable(host);
        }
    }
    private static void unavailable(Activity host) {
        Toast.makeText(host, "This native entry is not configured or is unavailable", Toast.LENGTH_LONG).show();
    }
}
