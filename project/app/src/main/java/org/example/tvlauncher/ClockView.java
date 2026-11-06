package org.example.tvlauncher;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Typeface;
import android.view.View;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

final class ClockView extends View {
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final SimpleDateFormat time = new SimpleDateFormat("HH:mm", Locale.getDefault());
    private final SimpleDateFormat date = new SimpleDateFormat("MMM d, EEEE", Locale.getDefault());
    private final Runnable tick = this::invalidate;
    private boolean active;

    ClockView(Context context) { super(context); setFocusable(false); }
    void setActive(boolean value) {
        active = value;
        removeCallbacks(tick);
        if (value) invalidate();
    }
    @Override protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        float scale = getWidth() / 960f, cx = getWidth() * .5f;
        Date now = new Date();
        paint.setTextAlign(Paint.Align.CENTER);
        paint.setTypeface(Typeface.create("sans-serif-light", Typeface.NORMAL));
        paint.setColor(0xffe1eeee);
        paint.setTextSize(30f * scale);
        canvas.drawText(time.format(now), cx, getHeight() * .80f, paint);
        paint.setTextSize(12f * scale);
        paint.setColor(0xff809fa7);
        canvas.drawText(date.format(now), cx, getHeight() * .853f, paint);
        removeCallbacks(tick);
        if (active && isShown()) postDelayed(tick, 1000);
    }
    @Override protected void onDetachedFromWindow() {
        removeCallbacks(tick);
        super.onDetachedFromWindow();
    }
}
