package org.example.tvlauncher;

public final class DrawerNavigationTest {
    private static void equal(int actual, int expected, String label) {
        if (actual != expected) throw new AssertionError(label + ": " + actual + " != " + expected);
    }
    public static void main(String[] args) {
        int[] counts = {0, 1, 12, 13, 24, 25};
        int[] pages = {1, 1, 1, 2, 2, 3};
        for (int i = 0; i < counts.length; i++) equal(DrawerNavigation.pageCount(counts[i]), pages[i], "page count");
        equal(DrawerNavigation.horizontal(25, 5, 1), 12, "right first row crosses page");
        equal(DrawerNavigation.horizontal(25, 11, 1), 18, "right keeps second row");
        equal(DrawerNavigation.horizontal(13, 11, 1), 12, "short last page clamps focus");
        equal(DrawerNavigation.horizontal(25, 12, -1), 5, "left first row crosses page");
        equal(DrawerNavigation.horizontal(25, 18, -1), 11, "left keeps second row");
        equal(DrawerNavigation.horizontal(25, 24, 1), 24, "last page never wraps");
        equal(DrawerNavigation.horizontal(25, 0, -1), 0, "first page never wraps");
        equal(DrawerNavigation.vertical(14, 5, 1), 11, "down same column");
        equal(DrawerNavigation.vertical(14, 12, 1), 12, "incomplete last page has no empty focus");
        equal(DrawerNavigation.vertical(8, 5, 1), 7, "short second row clamps column");
        for (int count = 1; count <= 80; count++) for (int index = 0; index < count; index++) {
            for (int direction : new int[]{-1, 1}) {
                int h = DrawerNavigation.horizontal(count, index, direction);
                int v = DrawerNavigation.vertical(count, index, direction);
                if (h < 0 || h >= count || v < 0 || v >= count) throw new AssertionError("Out of bounds focus");
                if (Math.abs(h / 12 - index / 12) > 1) throw new AssertionError("Skipped page");
            }
        }
        System.out.println("Drawer navigation: page edges, short pages, no wrapping and 80 list sizes passed.");
    }
}
