package org.example.tvlauncher;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RectF;
import android.view.View;

/** Handwritten geometric placeholder: no imported logos, bitmaps or particle data. */
final class GeometrySceneView extends View {
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final RectF rectangle = new RectF();
    private final IntroPlayback intro = new IntroPlayback();
    private Runnable introFinished;
    private boolean animating, symbolVisible = true, panelMode, saver;
    private long previousFrameNanos;
    private float visibleSeconds;

    GeometrySceneView(Context context) {
        super(context);
        setFocusable(false);
        setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);
    }

    void setIntroFinishedListener(Runnable listener) { introFinished = listener; }
    void playIntro() { intro.play(); previousFrameNanos = 0; invalidate(); }
    void finishIntro() { intro.cancel(); invalidate(); }
    void setSymbolVisible(boolean value) { symbolVisible = value; invalidate(); }
    void setPanelMode(boolean value) { panelMode = value; invalidate(); }
    void setScreenSaver(boolean value) { saver = value; invalidate(); }
    void setAnimating(boolean value) {
        animating = value;
        // Never include time spent behind another window in the next frame.
        previousFrameNanos = 0;
        if (value) postInvalidateOnAnimation();
    }

    @Override protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        long now = System.nanoTime();
        boolean active = animating && isShown() && hasWindowFocus();
        float delta = active && previousFrameNanos != 0
                ? Math.min(0.05f, Math.max(0f, (now - previousFrameNanos) / 1_000_000_000f)) : 0f;
        previousFrameNanos = active ? now : 0;
        visibleSeconds += delta;
        int token = intro.advance(delta);

        canvas.drawColor(Color.rgb(8, 13, 17));
        if (symbolVisible) {
            float progress = Math.min(1f, intro.seconds() / IntroPlayback.DURATION_SECONDS);
            float settle = progress * progress * (3f - 2f * progress);
            float scale = Math.min(getWidth() / 960f, getHeight() / 540f);
            float cx = getWidth() * (saver ? .5f : .72f);
            float cy = getHeight() * (saver ? .42f : .48f);
            // Small motion is application-local and stops when it loses focus.
            cx += (float) Math.sin(visibleSeconds * .13f) * 14f * scale;
            cy += (float) Math.cos(visibleSeconds * .11f) * 9f * scale;
            float radius = (62f + 18f * settle) * scale;
            paint.setStyle(Paint.Style.STROKE);
            paint.setStrokeWidth(3f * scale);
            paint.setColor(panelMode ? 0x446b9ba2 : 0xff87b9bd);
            canvas.save();
            canvas.rotate((1f - settle) * 60f, cx, cy);
            rectangle.set(cx - radius, cy - radius, cx + radius, cy + radius);
            canvas.drawRoundRect(rectangle, 18f * scale, 18f * scale, paint);
            canvas.restore();
            paint.setColor(panelMode ? 0x44cee2e1 : 0xffcee2e1);
            canvas.drawCircle(cx, cy, (16f + settle * 8f) * scale, paint);
        }

        // Post only after the final state has been drawn. A stale completion token
        // cannot reveal Home after cancellation or after a replacement intro.
        if (token != 0) post(() -> {
            if (intro.isCurrent(token) && introFinished != null) introFinished.run();
        });
        if (active) postInvalidateOnAnimation();
    }

    @Override protected void onDetachedFromWindow() {
        animating = false;
        previousFrameNanos = 0;
        super.onDetachedFromWindow();
    }
}
