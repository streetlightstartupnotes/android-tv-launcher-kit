package org.example.tvlauncher;

public final class OwnedKeyPressTest {
    private static int checks;
    private static void check(boolean value,String label){if(!value)throw new AssertionError(label);checks++;}
    private static boolean down(OwnedKeyPress p,int key,long at){return p.accept(key,0,at,0,false);}
    private static boolean up(OwnedKeyPress p,int key,long at){return p.accept(key,1,at,0,false);}
    public static void main(String[] args){
        OwnedKeyPress p=new OwnedKeyPress();
        check(!up(p,82,100),"orphan MENU UP does not open settings");
        check(!down(p,82,100),"MENU DOWN only arms");
        check(up(p,82,100),"matching UP opens once");
        check(!up(p,82,100),"duplicate UP does not reopen");
        down(p,82,200);p.reset();
        check(!up(p,82,200),"HOME/new intent invalidates old MENU");
        down(p,23,300);p.reset();
        check(!up(p,23,300),"focus loss prevents old confirmation from dismissing a new screen");
        down(p,82,400);
        check(!p.accept(82,1,400,0,true),"framework-canceled UP does not perform a second action");
        check(!up(p,82,400),"canceled pair stays consumed");
        p.accept(82,0,500,0,true);
        check(!up(p,82,500),"canceled DOWN never arms");
        down(p,82,600);
        check(!p.accept(82,0,600,1,false),"repeat DOWN cannot invoke action");
        check(up(p,82,600),"held press releases once");
        down(p,21,700);
        check(!up(p,22,700),"different direction cannot complete a press");
        check(!up(p,21,700),"mismatched UP consumes stale state");
        down(p,23,800);
        check(!up(p,23,801),"UP must have matching downTime");
        for(int key:new int[]{19,20,21,22,23,4,66,111,62,96,97}){
            down(p,key,1000+key);check(up(p,key,1000+key),"screensaver exits once for key "+key);
            check(!up(p,key,1000+key),"screensaver duplicate is ignored for key "+key);
        }
        check(!p.acceptMenu(82,0,1900,0,true,30001,-1),"default adapter rejects canceled relay DOWN");
        check(!p.acceptMenu(82,1,1900,0,true,30001,-1),"default adapter rejects canceled relay UP");
        p=new OwnedKeyPress(true); // Explicitly enable the narrowly scoped firmware adapter.
        check(!p.acceptMenu(82,0,2000,0,true,30001,-1),"observed vendor MENU DOWN arms without triggering");
        check(p.acceptMenu(82,1,2000,0,true,30001,-1),"observed vendor MENU pair opens settings once");
        check(!p.acceptMenu(82,1,2000,0,true,30001,-1),"vendor duplicate release is ignored");
        p.acceptMenu(82,0,2100,0,true,30001,-1);p.reset();
        check(!p.acceptMenu(82,1,2100,0,true,30001,-1),"vendor press cannot survive focus loss");
        p.acceptMenu(82,0,2200,0,true,32,-1);
        check(!p.acceptMenu(82,1,2200,0,true,32,-1),"ordinary canceled MENU remains rejected");
        p.acceptMenu(21,0,2300,0,true,30001,-1);
        check(!p.acceptMenu(21,1,2300,0,true,30001,-1),"vendor exception never changes DPAD");
        p.acceptMenu(82,0,2400,0,true,30001,2);
        check(!p.acceptMenu(82,1,2400,0,true,30001,2),"other device signature remains canceled");
        p.acceptMenu(82,0,2500,0,true,30001,-1);
        check(!p.acceptMenu(82,1,2501,0,true,30001,-1),"vendor pair still requires matching downTime");
        System.out.println("OwnedKeyPress: "+checks+" lifecycle, cancellation and discrete-action checks passed");
    }
}
