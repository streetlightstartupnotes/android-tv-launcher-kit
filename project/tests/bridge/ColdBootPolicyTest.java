package org.example.tvlauncher.bridge;
public final class ColdBootPolicyTest {
    static int checks;
    static void check(boolean v, String why) { if(!v)throw new AssertionError(why);checks++; }
    public static void main(String[] args) {
        check(ColdBootPolicy.allows(true,12,13,45000),"new boot within startup window");
        check(!ColdBootPolicy.allows(false,12,13,45000),"first run only establishes baseline");
        check(!ColdBootPolicy.allows(true,13,13,45000),"duplicate startup cannot relaunch");
        check(!ColdBootPolicy.allows(true,13,13,400000),"standby does not change boot count");
        check(!ColdBootPolicy.allows(true,12,13,180000),"late callback rejected at boundary");
        check(!ColdBootPolicy.allows(true,12,13,999999),"delayed callback cannot steal screen");
        check(!ColdBootPolicy.allows(true,-1,13,45000),"missing previous counter");
        check(!ColdBootPolicy.allows(true,12,-1,45000),"missing current counter");
        check(!ColdBootPolicy.allows(true,13,12,45000),"reset counter");
        check(!ColdBootPolicy.allows(true,12,13,-1),"invalid elapsed time");
        check(ColdBootPolicy.withinFirstFocusWindow(42000,49999),"focus before deadline qualifies");
        check(!ColdBootPolicy.withinFirstFocusWindow(42000,50000),"exact deadline rejects focus");
        check(!ColdBootPolicy.withinFirstFocusWindow(42000,51001),"late focus rejects even before timeout dispatch");
        check(!ColdBootPolicy.withinFirstFocusWindow(42000,41999),"backwards clock rejects focus");
        check(!ColdBootPolicy.withinFirstFocusWindow(-1,0),"invalid start rejects focus");
        System.out.println("ColdBootPolicy: "+checks+" checks passed");
    }
}
