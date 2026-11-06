package org.example.tvlauncher;

/** Pure navigation rules for the six-column TV application drawer. */
final class DrawerNavigation {
    static final int COLUMNS = 6, PAGE_SIZE = 12;
    static int pageCount(int count) { return Math.max(1, (Math.max(0, count) + PAGE_SIZE - 1) / PAGE_SIZE); }
    static int clampIndex(int count, int index) { return count == 0 ? -1 : Math.max(0, Math.min(count - 1, index)); }
    static int pageTarget(int count, int index, int delta) {
        if (count == 0) return -1;
        index = clampIndex(count, index);
        int page = index / PAGE_SIZE, targetPage = page + delta;
        if (targetPage < 0 || targetPage >= pageCount(count)) return index;
        int row = (index % PAGE_SIZE) / COLUMNS;
        int column = delta > 0 ? 0 : COLUMNS - 1;
        return Math.min(count - 1, targetPage * PAGE_SIZE + row * COLUMNS + column);
    }
    static int horizontal(int count, int index, int direction) {
        if (count == 0) return -1;
        index = clampIndex(count, index);
        int column = index % COLUMNS;
        if (direction > 0) {
            if (column < COLUMNS - 1 && index + 1 < count) return index + 1;
            return pageTarget(count, index, 1);
        }
        if (column > 0) return index - 1;
        return pageTarget(count, index, -1);
    }
    static int vertical(int count, int index, int direction) {
        if (count == 0) return -1;
        index = clampIndex(count, index);
        int local = index % PAGE_SIZE;
        if (direction < 0) return local >= COLUMNS ? index - COLUMNS : index;
        if (local >= COLUMNS) return index;
        int secondRowStart = index / PAGE_SIZE * PAGE_SIZE + COLUMNS;
        return secondRowStart < count ? Math.min(count - 1, index + COLUMNS) : index;
    }
}
