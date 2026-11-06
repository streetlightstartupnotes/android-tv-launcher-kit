package org.example.tvlauncher;

import android.app.Activity;
import android.content.ComponentName;
import android.content.Intent;
import android.content.pm.ResolveInfo;
import android.graphics.*;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.*;
import android.view.animation.DecelerateInterpolator;
import android.widget.*;
import java.text.SimpleDateFormat;
import java.util.*;

/** An application-owned TV home, app drawer, settings panel and manual saver. */
public final class MainActivity extends Activity {
    static final int WHITE=0xfff4f5ed, MUTED=0xffa9b5af, ICE=0xffebf6f6;
    private final Handler handler=new Handler(Looper.getMainLooper());
    private final DecelerateInterpolator ease=new DecelerateInterpolator();
    private final SimpleDateFormat timeFormat=new SimpleDateFormat("HH:mm",Locale.getDefault());
    private final SimpleDateFormat dateFormat=new SimpleDateFormat("MMM d, EEEE",Locale.getDefault());
    private FrameLayout root,chrome;
    private View panel;
    private LinearLayout appPager;
    private boolean appsOpen,pageAnimating,bootOpening,bootFrameComplete,settingsFromApps;
    private OwnedKeyPress menuPress;
    private final OwnedKeyPress saverExitPress=new OwnedKeyPress();
    private int focusedAppIndex,pageLatchKey;
    private String focusedAppId="";
    private final ArrayList<View> appCells=new ArrayList<>();
    private GeometrySceneView scene;
    private ClockView saverClock;
    private TextView clock,date,pageCount,previousPage,nextPage;
    private boolean saver,resumed;
    private final Runnable bootReveal=()->{
        if(bootOpening&&bootFrameComplete&&resumed&&hasWindowFocus()){
            bootOpening=false;bootFrameComplete=false;scene.finishIntro();applySaver(false,true);
        }
    };
    private final ArrayList<NavIcon> nav=new ArrayList<>();
    private final ArrayList<AppItem> drawerApps=new ArrayList<>();
    private GridLayout appGrid;
    private int appPage,activeNav;
    private final Runnable idle=()->setSaver(true);
    private final Runnable tick=new Runnable(){public void run(){
        Date now=new Date();clock.setText(timeFormat.format(now));date.setText(dateFormat.format(now));
        if(resumed)handler.postDelayed(this,1000);
    }};

    int dp(float value){return Math.round(value*getResources().getDisplayMetrics().density);}
    TextView text(String value,float size,int color){
        TextView view=new TextView(this);view.setText(value);view.setTextSize(size);view.setTextColor(color);
        view.setIncludeFontPadding(false);view.setTypeface(Typeface.create("sans-serif",Typeface.NORMAL));return view;
    }
    GradientDrawable surface(int color,float radius){
        GradientDrawable d=new GradientDrawable();d.setColor(color);d.setCornerRadius(dp(radius));return d;
    }
    GradientDrawable focusSurface(boolean focus,float radius){
        GradientDrawable d=surface(focus?0x12ffffff:0,radius);
        if(focus)d.setStroke(dp(.65f),0x4dcee2e1);return d;
    }
    @Override public void onCreate(Bundle state){
        super.onCreate(state);
        menuPress=new OwnedKeyPress(getResources().getBoolean(R.bool.enable_vendor_menu_relay));
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        getWindow().getDecorView().setSystemUiVisibility(5894);
        root=new FrameLayout(this);root.setBackgroundColor(0xff080d11);
        scene=new GeometrySceneView(this);scene.setAnimating(false);
        scene.setIntroFinishedListener(()->{if(bootOpening){bootFrameComplete=true;bootReveal.run();}});
        root.addView(scene,new FrameLayout.LayoutParams(-1,-1));
        chrome=new FrameLayout(this);root.addView(chrome,new FrameLayout.LayoutParams(-1,-1));
        buildHome();
        saverClock=new ClockView(this);saverClock.setVisibility(View.GONE);
        root.addView(saverClock,new FrameLayout.LayoutParams(-1,-1));
        setContentView(root);nav.get(0).requestFocus();
        focusedAppId=getSharedPreferences("drawer",MODE_PRIVATE).getString("appId","");
        focusedAppIndex=getSharedPreferences("drawer",MODE_PRIVATE).getInt("appIndex",0);
        if(getIntent().getBooleanExtra("home_key",false)){
            applySaver(false,false);
        }else if(state!=null){
            activeNav=Math.max(0,Math.min(nav.size()-1,state.getInt("nav",0)));
            if(state.getBoolean("settingsOpen",false)){
                settingsPanel();settingsFromApps=state.getBoolean("settingsFromApps",false);
            }else if(state.getBoolean("appsOpen",false))appsPanel();
            else if(state.getBoolean("saver",false))applySaver(true,false);
            else nav.get(activeNav).requestFocus();
        }else if(getIntent().getBooleanExtra("boot_scene",false))startBootScene();
        getIntent().removeExtra("boot_scene");
        getIntent().removeExtra("home_key");
        if(getIntent().getBooleanExtra("native_menu",false)){
            getIntent().removeExtra("native_menu");handler.post(this::showNativeMenu);
        }
    }
    private void buildHome(){
        LinearLayout times=new LinearLayout(this);times.setOrientation(LinearLayout.VERTICAL);
        clock=text("",80,WHITE);clock.setTypeface(Typeface.create("sans-serif",Typeface.NORMAL));
        clock.setFontFeatureSettings("tnum");clock.setSingleLine(true);times.addView(clock,new LinearLayout.LayoutParams(-1,-2));
        date=text("",14,0xffd6d8d2);date.setTypeface(Typeface.create("sans-serif-medium",Typeface.NORMAL));
        LinearLayout.LayoutParams dateLp=new LinearLayout.LayoutParams(-1,-2);dateLp.topMargin=dp(5);times.addView(date,dateLp);
        TextView name=text(getString(R.string.app_name),20,WHITE);
        LinearLayout.LayoutParams nameLp=new LinearLayout.LayoutParams(-2,-2);
        nameLp.topMargin=dp(22);times.addView(name,nameLp);
        FrameLayout.LayoutParams timeLp=new FrameLayout.LayoutParams(dp(400),-2);
        timeLp.leftMargin=dp(48);timeLp.topMargin=dp(29);chrome.addView(times,timeLp);

        LinearLayout dock=new LinearLayout(this);dock.setOrientation(LinearLayout.HORIZONTAL);
        String[] labels={"Apps","Settings","Screen saver","Inputs","Original home"};
        for(int i=0;i<labels.length;i++){
            final int index=i;NavIcon icon=new NavIcon(labels[i],i);icon.setContentDescription(labels[i]);
            icon.setOnClickListener(v->activate(index));icon.setOnFocusChangeListener((v,f)->{if(f)activeNav=index;icon.invalidate();});
            dock.addView(icon,new LinearLayout.LayoutParams(0,dp(62),1));nav.add(icon);
        }
        FrameLayout.LayoutParams dockLp=new FrameLayout.LayoutParams(dp(385),dp(62),Gravity.LEFT|Gravity.BOTTOM);
        dockLp.leftMargin=dp(29);dockLp.bottomMargin=dp(29);chrome.addView(dock,dockLp);

    }

    private void activate(int index){activeNav=index;switch(index){
        case 0:appsPanel();break;
        case 1:settingsPanel();break;
        case 2:setSaver(true);break;
        case 3:NativeEntries.openInputs(this);break;
        case 4:originalHome();break;
    }}
    void open(Intent intent){
        if(!resumed||!hasWindowFocus())return;
        try{startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));}
        catch(RuntimeException e){Toast.makeText(this,"This entry is unavailable",Toast.LENGTH_LONG).show();}
    }
    void originalHome(){NativeEntries.openOriginalHome(this);}
    void settingsPanel(){
        boolean fromApps=appsOpen;
        removePanel();handler.removeCallbacks(idle);chrome.setVisibility(View.INVISIBLE);
        settingsFromApps=fromApps;
        scene.setSymbolVisible(true);scene.setPanelMode(true);
        panel=new SettingsPanel(this);root.addView(panel,new FrameLayout.LayoutParams(-1,-1));
    }
    int idleSeconds(){return getSharedPreferences("display",MODE_PRIVATE).getInt("idleSeconds",0);}

    void addPageHeader(FrameLayout parent,String title,String section){
        TextView heading=text(title,23,WHITE);heading.setTypeface(Typeface.create("sans-serif-medium",Typeface.NORMAL));
        FrameLayout.LayoutParams titleLp=new FrameLayout.LayoutParams(-2,-2);titleLp.leftMargin=dp(64);titleLp.topMargin=dp(41);parent.addView(heading,titleLp);
        TextView back=text("‹   Back",12,0xffb7cdcf);back.setPadding(dp(12),dp(10),dp(12),dp(10));back.setFocusable(true);
        back.setOnClickListener(v->onBackPressed());back.setOnFocusChangeListener((v,f)->back.setBackground(focusSurface(f,7)));
        FrameLayout.LayoutParams backLp=new FrameLayout.LayoutParams(-2,-2,Gravity.TOP|Gravity.RIGHT);backLp.rightMargin=dp(53);backLp.topMargin=dp(33);parent.addView(back,backLp);
    }
    final class AppItem{
        final String id,name;final Drawable icon;final Runnable action;
        AppItem(String id,String name,Drawable icon,Runnable action){this.id=id;this.name=name;this.icon=icon;this.action=action;}
    }
    void appsPanel(){
        removePanel();appsOpen=true;handler.removeCallbacks(idle);chrome.setVisibility(View.INVISIBLE);
        scene.setPanelMode(false);scene.setSymbolVisible(false);
        FrameLayout shade=new FrameLayout(this);shade.setBackgroundColor(0x1403080c);panel=shade;
        root.addView(shade,new FrameLayout.LayoutParams(-1,-1));addPageHeader(shade,"Apps","");
        appGrid=new GridLayout(this);appGrid.setColumnCount(DrawerNavigation.COLUMNS);
        FrameLayout.LayoutParams gridLp=new FrameLayout.LayoutParams(-1,-2);
        gridLp.leftMargin=dp(57);gridLp.rightMargin=dp(57);gridLp.topMargin=dp(105);shade.addView(appGrid,gridLp);
        appPager=new LinearLayout(this);appPager.setGravity(Gravity.CENTER);
        pageCount=text("",12,0xffc8e0df);pageCount.setGravity(Gravity.CENTER);
        previousPage=text("‹",27,MUTED);nextPage=text("›",27,MUTED);
        for(TextView arrow:new TextView[]{previousPage,nextPage}){
            arrow.setGravity(Gravity.CENTER);arrow.setFocusable(true);
            arrow.setOnFocusChangeListener((v,f)->arrow.setTextColor(f?ICE:MUTED));
        }
        previousPage.setContentDescription("Previous page");nextPage.setContentDescription("Next page");
        previousPage.setOnClickListener(v->changeAppPage(-1));nextPage.setOnClickListener(v->changeAppPage(1));
        appPager.addView(previousPage,new LinearLayout.LayoutParams(dp(42),dp(36)));
        appPager.addView(pageCount,new LinearLayout.LayoutParams(dp(90),dp(36)));
        appPager.addView(nextPage,new LinearLayout.LayoutParams(dp(42),dp(36)));
        FrameLayout.LayoutParams pagerLp=new FrameLayout.LayoutParams(-2,dp(36),Gravity.BOTTOM|Gravity.CENTER_HORIZONTAL);
        pagerLp.bottomMargin=dp(20);shade.addView(appPager,pagerLp);
        loadApps();restoreAppAnchor();renderPage(focusedAppIndex/DrawerNavigation.PAGE_SIZE,focusedAppIndex);
        animatePanel(shade);
    }
    void animatePanel(View view){view.setAlpha(0f);view.setTranslationY(dp(7));view.animate().alpha(1f).translationY(0f).setDuration(250).setInterpolator(ease).start();}
    private void loadApps(){
        drawerApps.clear();
        Drawable genericIcon=getDrawable(R.drawable.quiet_icon);
        drawerApps.add(new AppItem("local:settings","Settings",genericIcon,this::settingsPanel));
        if(NativeEntries.hasOriginalHome(this))
            drawerApps.add(new AppItem("local:original-home","Original home",genericIcon,this::originalHome));
        LinkedHashMap<String,ResolveInfo> apps=new LinkedHashMap<>();
        String originalPackage=NativeEntries.originalHomePackage(this);
        for(String category:new String[]{Intent.CATEGORY_LEANBACK_LAUNCHER,Intent.CATEGORY_LAUNCHER}){
            Intent query=new Intent(Intent.ACTION_MAIN).addCategory(category);
            for(ResolveInfo result:getPackageManager().queryIntentActivities(query,0)){
                String pkg=result.activityInfo.packageName;
                if(pkg.equals(getPackageName())||pkg.equals(originalPackage)||pkg.equals("org.example.tvlauncher.bridge"))continue;
                if(!apps.containsKey(pkg))apps.put(pkg,result);
            }
        }
        ArrayList<Map.Entry<String,ResolveInfo>> sorted=new ArrayList<>(apps.entrySet());
        java.text.Collator collator=java.text.Collator.getInstance(Locale.getDefault());
        sorted.sort((a,b)->collator.compare(a.getValue().loadLabel(getPackageManager()).toString(),b.getValue().loadLabel(getPackageManager()).toString()));
        for(Map.Entry<String,ResolveInfo> entry:sorted){
            ResolveInfo app=entry.getValue();
            Runnable action=()->open(new Intent(Intent.ACTION_MAIN).setComponent(new ComponentName(app.activityInfo.packageName,app.activityInfo.name)));
            drawerApps.add(new AppItem(entry.getKey(),app.loadLabel(getPackageManager()).toString(),app.loadIcon(getPackageManager()),action));
        }
    }
    private void restoreAppAnchor(){
        for(int i=0;i<drawerApps.size();i++)if(drawerApps.get(i).id.equals(focusedAppId)){focusedAppIndex=i;return;}
        focusedAppIndex=Math.max(0,DrawerNavigation.clampIndex(drawerApps.size(),focusedAppIndex));
    }
    private void rememberAppFocus(int index){
        if(index<0||index>=drawerApps.size())return;
        focusedAppIndex=index;focusedAppId=drawerApps.get(index).id;
    }
    private void saveAppAnchor(){
        getSharedPreferences("drawer",MODE_PRIVATE).edit().putString("appId",focusedAppId).putInt("appIndex",focusedAppIndex).apply();
    }
    private void refreshDrawer(){
        if(!appsOpen||pageAnimating)return;
        StringBuilder before=new StringBuilder();for(AppItem item:drawerApps)before.append(item.id).append('\n').append(item.name).append('\n');
        loadApps();StringBuilder after=new StringBuilder();for(AppItem item:drawerApps)after.append(item.id).append('\n').append(item.name).append('\n');
        if(!before.toString().equals(after.toString())){restoreAppAnchor();renderPage(focusedAppIndex/12,focusedAppIndex);}
    }
    private void changeAppPage(int direction){
        if(pageAnimating)return;
        int target=DrawerNavigation.pageTarget(drawerApps.size(),focusedAppIndex,direction);
        if(target>=0&&target/12!=appPage)animateAppPage(target,direction);
    }
    private void animateAppPage(int target,int direction){
        if(pageAnimating||!appsOpen)return;
        pageAnimating=true;GridLayout grid=appGrid;
        grid.animate().cancel();
        grid.animate().translationX(-direction*dp(18)).alpha(0f).setDuration(100).setInterpolator(ease).withEndAction(()->{
            if(!appsOpen||appGrid!=grid){pageAnimating=false;return;}
            renderPage(target/12,target);grid.setTranslationX(direction*dp(18));grid.setAlpha(0f);
            grid.animate().translationX(0f).alpha(1f).setDuration(140).setInterpolator(ease).withEndAction(()->pageAnimating=false).start();
        }).start();
    }
    private void renderPage(int requested,int targetIndex){
        int pages=DrawerNavigation.pageCount(drawerApps.size());
        appPage=Math.max(0,Math.min(pages-1,requested));appGrid.removeAllViews();appCells.clear();
        appPager.setVisibility(pages>1?View.VISIBLE:View.GONE);
        pageCount.setText(String.format(Locale.getDefault(),"%d / %d",appPage+1,pages));
        previousPage.setEnabled(appPage>0);previousPage.setFocusable(appPage>0);previousPage.setAlpha(appPage>0?1f:.25f);
        nextPage.setEnabled(appPage+1<pages);nextPage.setFocusable(appPage+1<pages);nextPage.setAlpha(appPage+1<pages?1f:.25f);
        targetIndex=DrawerNavigation.clampIndex(drawerApps.size(),targetIndex);
        if(drawerApps.isEmpty()){
            TextView empty=text("No launchable apps",16,MUTED);appGrid.addView(empty);return;
        }
        for(int i=0;i<12;i++){
            GridLayout.LayoutParams lp=new GridLayout.LayoutParams(GridLayout.spec(i/6),GridLayout.spec(i%6,1f));
            lp.width=0;lp.height=dp(157);lp.setMargins(dp(6),0,dp(6),dp(8));
            final int index=appPage*12+i;
            if(index>=drawerApps.size()){
                View vacant=new View(this);vacant.setVisibility(View.INVISIBLE);vacant.setFocusable(false);
                appGrid.addView(vacant,lp);continue;
            }
            AppItem item=drawerApps.get(index);
            LinearLayout cell=new LinearLayout(this);cell.setOrientation(LinearLayout.VERTICAL);cell.setGravity(Gravity.TOP|Gravity.CENTER_HORIZONTAL);
            cell.setPadding(dp(5),dp(14),dp(5),dp(10));cell.setFocusable(true);cell.setClickable(true);cell.setTag(index);
            ImageView icon=new ImageView(this);icon.setImageDrawable(item.icon);icon.setScaleType(ImageView.ScaleType.FIT_CENTER);
            icon.setBackground(surface(0xff1a262b,13));icon.setClipToOutline(true);cell.addView(icon,new LinearLayout.LayoutParams(dp(70),dp(70)));
            TextView label=text(item.name,13,0xffbdccca);label.setSingleLine(true);label.setEllipsize(android.text.TextUtils.TruncateAt.END);label.setGravity(Gravity.CENTER);
            LinearLayout.LayoutParams labelLp=new LinearLayout.LayoutParams(-1,-2);labelLp.topMargin=dp(14);cell.addView(label,labelLp);
            cell.setOnFocusChangeListener((view,focus)->{
                if(focus)rememberAppFocus(index);
                cell.setBackground(focusSurface(focus,11));label.setTextColor(focus?WHITE:0xffaabfbd);
                icon.animate().scaleX(focus?1.045f:1).scaleY(focus?1.045f:1).translationY(focus?-dp(2):0).setDuration(170).setInterpolator(ease).start();
            });
            cell.setOnClickListener(v->{if(!pageAnimating){rememberAppFocus(index);saveAppAnchor();item.action.run();}});
            appGrid.addView(cell,lp);appCells.add(cell);
            if(index==targetIndex)cell.requestFocus();
        }
    }
    private boolean handleDrawerKey(KeyEvent event){
        int key=event.getKeyCode();
        if(event.getAction()==KeyEvent.ACTION_UP&&key==pageLatchKey){pageLatchKey=0;return true;}
        if(event.getAction()==KeyEvent.ACTION_DOWN&&event.getRepeatCount()==0)pageLatchKey=0;
        if(pageLatchKey==key)return true;
        boolean direction=key>=KeyEvent.KEYCODE_DPAD_UP&&key<=KeyEvent.KEYCODE_DPAD_RIGHT;
        if(pageAnimating&&(direction||key==KeyEvent.KEYCODE_DPAD_CENTER||key==KeyEvent.KEYCODE_ENTER))return true;
        View focus=getCurrentFocus();
        if(!direction||focus==null||!(focus.getTag() instanceof Integer))return false;
        int index=(Integer)focus.getTag();
        if(event.getAction()!=KeyEvent.ACTION_DOWN)return true;
        int target=index;
        if(key==KeyEvent.KEYCODE_DPAD_LEFT||key==KeyEvent.KEYCODE_DPAD_RIGHT){
            int delta=key==KeyEvent.KEYCODE_DPAD_RIGHT?1:-1;
            target=DrawerNavigation.horizontal(drawerApps.size(),index,delta);
            if(target/12!=appPage){pageLatchKey=key;animateAppPage(target,delta);return true;}
        }else{
            target=DrawerNavigation.vertical(drawerApps.size(),index,key==KeyEvent.KEYCODE_DPAD_DOWN?1:-1);
            if(target==index){
                if(key==KeyEvent.KEYCODE_DPAD_UP)return false;
                if(nextPage.isEnabled())nextPage.requestFocus();else if(previousPage.isEnabled())previousPage.requestFocus();
                return true;
            }
        }
        int child=target-appPage*12;if(child>=0&&child<appCells.size())appCells.get(child).requestFocus();
        return true;
    }
    private void removePanel(){
        if(appsOpen)saveAppAnchor();
        appsOpen=false;pageAnimating=false;pageLatchKey=0;settingsFromApps=false;
        if(appGrid!=null)appGrid.animate().cancel();
        if(panel!=null){panel.animate().cancel();root.removeView(panel);panel=null;}
    }
    void closePanel(){
        if(panel==null)return;removePanel();scene.setPanelMode(false);scene.setSymbolVisible(true);
        chrome.setVisibility(saver?View.GONE:View.VISIBLE);chrome.setAlpha(1);chrome.setTranslationY(0);nav.get(activeNav).requestFocus();armIdle();
    }
    private void startBootScene(){
        if(bootOpening)return;
        boolean preview=getIntent().getBooleanExtra("preview_intro",false);getIntent().removeExtra("preview_intro");
        int boot=-1;
        try{boot=android.provider.Settings.Global.getInt(getContentResolver(),"boot_count",-1);}catch(RuntimeException ignored){}
        android.content.SharedPreferences intro=getSharedPreferences("intro",MODE_PRIVATE);
        if(!preview&&boot>=0&&intro.getInt("presentedBoot",-2)==boot){removePanel();applySaver(false,false);return;}
        if(boot>=0)intro.edit().putInt("presentedBoot",boot).apply();
        removePanel();bootOpening=true;bootFrameComplete=false;
        // The intro owns this app window only. Completion reveals the home layout.
        scene.setAnimating(resumed&&hasWindowFocus());scene.setSymbolVisible(true);scene.setPanelMode(false);
        scene.playIntro();applySaver(true,false);saverClock.setVisibility(View.INVISIBLE);saverClock.setAlpha(0f);
    }
    private void cancelBootScene(){
        if(!bootOpening)return;bootOpening=false;bootFrameComplete=false;scene.finishIntro();
    }
    void setSaver(boolean enabled){if(!resumed||!hasWindowFocus())return;cancelBootScene();closePanel();applySaver(enabled,true);}
    void showNativeMenu(){
        if(!resumed||!hasWindowFocus())return;
        cancelBootScene();if(saver)applySaver(false,true);handler.removeCallbacks(idle);
        NativeEntries.openMenu(this);
    }
    private void applySaver(boolean enabled,boolean animate){
        menuPress.reset();saverExitPress.reset();
        saver=enabled;scene.setPanelMode(false);scene.setSymbolVisible(true);scene.setScreenSaver(enabled);
        chrome.animate().cancel();saverClock.animate().cancel();handler.removeCallbacks(idle);
        if(!animate){chrome.setVisibility(enabled?View.GONE:View.VISIBLE);chrome.setAlpha(1);chrome.setTranslationY(0);saverClock.setVisibility(enabled?View.VISIBLE:View.GONE);saverClock.setAlpha(1);return;}
        if(enabled){
            chrome.animate().alpha(0f).translationY(-dp(6)).setStartDelay(0).setDuration(240).setInterpolator(ease).withEndAction(()->{if(saver)chrome.setVisibility(View.INVISIBLE);}).start();
            saverClock.setVisibility(View.VISIBLE);saverClock.setAlpha(0f);saverClock.animate().alpha(1f).setStartDelay(360).setDuration(480).setInterpolator(ease).start();
        }else{
            saverClock.animate().alpha(0f).setStartDelay(0).setDuration(180).withEndAction(()->{if(!saver)saverClock.setVisibility(View.GONE);}).start();
            chrome.setVisibility(View.VISIBLE);chrome.setAlpha(0f);chrome.setTranslationY(-dp(5));
            chrome.animate().alpha(1f).translationY(0).setStartDelay(220).setDuration(440).setInterpolator(ease).start();
            for(NavIcon icon:nav)icon.invalidate();armIdle();
        }
    }
    void armIdle(){handler.removeCallbacks(idle);int seconds=idleSeconds();if(resumed&&hasWindowFocus()&&!saver&&panel==null&&seconds>0)handler.postDelayed(idle,seconds*1000L);}
    @Override protected void onResume(){
        super.onResume();resumed=true;scene.setAnimating(hasWindowFocus());saverClock.setActive(hasWindowFocus());bootReveal.run();
        refreshDrawer();handler.removeCallbacks(tick);tick.run();armIdle();
    }
    @Override protected void onPause(){
        resumed=false;pageLatchKey=0;menuPress.reset();saverExitPress.reset();saverClock.setActive(false);saveAppAnchor();handler.removeCallbacks(tick);handler.removeCallbacks(idle);
        if(bootOpening){cancelBootScene();applySaver(false,false);}scene.setAnimating(false);super.onPause();
    }
    @Override public void onWindowFocusChanged(boolean focused){
        super.onWindowFocusChanged(focused);if(scene!=null)scene.setAnimating(resumed&&focused);if(saverClock!=null)saverClock.setActive(resumed&&focused);
        if(focused){bootReveal.run();armIdle();}else{pageLatchKey=0;menuPress.reset();saverExitPress.reset();handler.removeCallbacks(idle);}
    }
    @Override protected void onSaveInstanceState(Bundle state){
        state.putBoolean("appsOpen",appsOpen);state.putBoolean("saver",saver);state.putInt("nav",activeNav);
        state.putBoolean("settingsOpen",panel instanceof SettingsPanel);state.putBoolean("settingsFromApps",settingsFromApps);
        saveAppAnchor();super.onSaveInstanceState(state);
    }
    @Override protected void onNewIntent(Intent intent){
        super.onNewIntent(intent);setIntent(intent);menuPress.reset();saverExitPress.reset();pageLatchKey=0;
        if(intent.getBooleanExtra("boot_scene",false)){startBootScene();intent.removeExtra("boot_scene");}
        else if(intent.getBooleanExtra("home_key",false)){intent.removeExtra("home_key");cancelBootScene();removePanel();applySaver(false,true);}
        if(intent.getBooleanExtra("native_menu",false)){intent.removeExtra("native_menu");showNativeMenu();}
    }
    @Override public void onUserInteraction(){
        super.onUserInteraction();armIdle();
    }
    public static boolean isSaverExitKey(int key){
        switch(key){
            case KeyEvent.KEYCODE_DPAD_UP:case KeyEvent.KEYCODE_DPAD_DOWN:
            case KeyEvent.KEYCODE_DPAD_LEFT:case KeyEvent.KEYCODE_DPAD_RIGHT:
            case KeyEvent.KEYCODE_DPAD_CENTER:case KeyEvent.KEYCODE_ENTER:
            case KeyEvent.KEYCODE_BACK:case KeyEvent.KEYCODE_ESCAPE:case KeyEvent.KEYCODE_MENU:
            case KeyEvent.KEYCODE_SPACE:case KeyEvent.KEYCODE_BUTTON_A:case KeyEvent.KEYCODE_BUTTON_B:return true;
            default:return false;
        }
    }
    @Override public boolean dispatchKeyEvent(KeyEvent event){
        int key=event.getKeyCode();
        if(!resumed||!hasWindowFocus()){menuPress.reset();saverExitPress.reset();return super.dispatchKeyEvent(event);}
        if(key!=KeyEvent.KEYCODE_MENU&&event.getAction()==KeyEvent.ACTION_DOWN)menuPress.reset();
        if(key==KeyEvent.KEYCODE_MENU){
            if(menuPress.acceptMenu(key,event.getAction(),event.getDownTime(),event.getRepeatCount(),event.isCanceled(),event.getFlags(),event.getDeviceId()))showNativeMenu();
            return true;
        }
        if(saver&&isSaverExitKey(key)){
            if(saverExitPress.accept(key,event.getAction(),event.getDownTime(),event.getRepeatCount(),event.isCanceled()))setSaver(false);
            return true;
        }
        if(appsOpen&&handleDrawerKey(event))return true;
        return super.dispatchKeyEvent(event);
    }
    @Override public void onBackPressed(){
        menuPress.reset();saverExitPress.reset();
        if(saver)setSaver(false);
        else if(panel instanceof SettingsPanel&&((SettingsPanel)panel).handleBack())return;
        else if(panel instanceof SettingsPanel&&settingsFromApps)appsPanel();
        else if(panel!=null)closePanel();
    }

    final class NavIcon extends View{
        final String label;final int kind;final Paint paint=new Paint(3);final RectF rect=new RectF();final Path path=new Path();
        NavIcon(String label,int kind){super(MainActivity.this);this.label=label;this.kind=kind;setFocusable(true);setClickable(true);}
        @Override protected void onDraw(Canvas canvas){
            float x=getWidth()/2f,y=dp(23);boolean focus=isFocused();
            paint.setStyle(Paint.Style.FILL);
            if(focus){paint.setColor(0x0e87dff7);rect.set(x-dp(24),y-dp(23),x+dp(24),y+dp(23));canvas.drawRoundRect(rect,dp(8),dp(8),paint);}
            canvas.save();canvas.translate(x,y);canvas.scale(dp(1),dp(1));
            paint.setColor(focus?ICE:0xffd7ded7);paint.setStrokeWidth(1.45f);paint.setStyle(Paint.Style.STROKE);paint.setStrokeCap(Paint.Cap.ROUND);paint.setStrokeJoin(Paint.Join.ROUND);
            switch(kind){
                case 0:for(int yy=-1;yy<=1;yy+=2)for(int xx=-1;xx<=1;xx+=2){rect.set(xx*4.5f-2.5f,yy*4.5f-2.5f,xx*4.5f+2.5f,yy*4.5f+2.5f);canvas.drawRoundRect(rect,.8f,.8f,paint);}break;
                case 1:for(int row=-1;row<=1;row++){float yy=row*5;canvas.drawLine(-8,yy,8,yy,paint);canvas.drawCircle(row==0?3:-3,yy,1.6f,paint);}break;
                case 2:rect.set(-9,-6,9,6);canvas.drawRoundRect(rect,2,2,paint);canvas.drawCircle(0,0,2,paint);break;
                case 3:canvas.drawLine(-9,0,7,0,paint);canvas.drawLine(3,-4,7,0,paint);canvas.drawLine(3,4,7,0,paint);break;
                case 4:path.reset();path.moveTo(-9,-1);path.lineTo(0,-8);path.lineTo(9,-1);path.moveTo(-6,-2);path.lineTo(-6,8);path.lineTo(6,8);path.lineTo(6,-2);canvas.drawPath(path,paint);break;
            }
            canvas.restore();paint.setStyle(Paint.Style.FILL);paint.setTextAlign(Paint.Align.CENTER);paint.setTypeface(Typeface.create("sans-serif",Typeface.NORMAL));paint.setTextSize(dp(10));paint.setColor(focus?0xffd6eef0:0xff66868d);canvas.drawText(label,x,dp(56),paint);
        }
    }
}
