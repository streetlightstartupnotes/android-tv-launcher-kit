# Quiet TV 示例工程

一个不含品牌素材和设备配置的 Android TV 原生 Java 示例。`app` 提供 Home、Settings、Apps 和手动屏保；`boot-bridge` 是可选的 HOME 转交应用。两个模块均使用 Android 平台 API，没有额外运行时依赖。

## 本地构建

使用已经安装的 JDK 17 或 21、Gradle 8.14.3、Android SDK Platform 34，以及 Android Gradle Plugin 8.13.0 所需的本地依赖。SDK 通过标准 `ANDROID_HOME` 环境变量或本机 `local.properties` 指定。不要把本机 `local.properties` 放进分享包。

从此目录执行：

```sh
python3 tools/test-logic.py
gradle --offline :app:assembleDebug :boot-bridge:assembleDebug
```

`--offline` 不下载依赖；缺少缓存时会失败。项目不携带 Gradle 分发包、Wrapper JAR、SDK、签名材料或 APK。已有完整工具环境的接收者可以直接构建。Debug 构建使用接收者自己的本地调试签名；发布签名由接收者另行配置。

若只需要独立检查资源、Java 和 DEX，可以传入现有本地工具：

```sh
python3 tools/verify-android.py \
  --android-jar "$ANDROID_HOME/platforms/android-34/android.jar" \
  --aapt2 "$AAPT2" \
  --d8-jar "$D8_JAR" \
  --jdk "$JAVA_HOME"
```

`AAPT2` 指向已安装的 aapt2 可执行文件，`D8_JAR` 指向包含 `com.android.tools.r8.D8` 的本地 JAR。使用拆分的 API 类库时，可加 `--framework "$ANDROID_FRAMEWORK"` 指定对应资源框架。脚本只在临时目录编译，结束后清除产物，不签名、安装、部署或联网。它不等于完整 Gradle 构建和设备验收；本次验证结果见 [VALIDATION.md](VALIDATION.md)。

## 模块与默认行为

| 位置 | 内容 |
| --- | --- |
| `app` / `org.example.tvlauncher` | 安装后可从电视应用列表打开的 Quiet TV |
| `boot-bridge` / `org.example.tvlauncher.bridge` | 单独的 HOME 候选入口；仅在真正获得前台焦点时转交给 Quiet TV |
| `tests/app` | 按键配对、动画生命周期、6 列 12 项分页逻辑 |
| `tests/bridge` | 冷启动、HOME 转交、超时、取消与按键逻辑 |
| `tools` | 不需要设备连接的离线验证脚本 |

Quiet TV 底部提供 Apps、Settings、Screen saver、Inputs、Original home。Settings 中的 Home idle saver 默认关闭；用户可以显式选择 1、2、5 或 10 分钟，只在此应用持有焦点的主页上计时。手动屏保收到匹配的方向键、确认键或返回键释放后退出；MENU 打开已配置的系统设置入口。

应用列表按应用包去重，保留最后聚焦的应用与位置；横向越过边缘时换页，纵向在短行上收敛到有效项目。安装或移除应用后，返回界面会刷新列表。界面使用重新手写的矩形、圆形和通用线条图标，没有导入图像、字体或粒子数据。

屏保和入场动画都在应用窗口内绘制。动画时间仅累加可见且持有焦点的帧；失焦会暂停，离开 Activity 会取消入场动画，旧完成回调无法揭开新的界面。`IntroPlayback` 独立于渲染方式，可迁移到其他 Canvas 或 GL 渲染器。

## 原生入口适配

配置集中在 `app/src/main/res/values/config.xml`：

| 配置 | 默认值 / 用途 |
| --- | --- |
| `native_menu_mode`、`native_menu_action`、`native_menu_component` | 默认以 Activity 打开公开的 `android.settings.SETTINGS` |
| `native_wifi_action`、`native_bluetooth_action`、`native_display_action` | 公开 Android 设置 Action；实际可用性仍由目标系统决定 |
| `native_inputs_*` | 默认空，未适配时只显示不可用提示 |
| `native_original_home_component` | 默认空；适配时填 `package/activity`，且必须是已验证可由第三方调用的组件 |
| `enable_vendor_menu_relay` | 默认 `false`，控制窄范围的固件 MENU 兼容逻辑 |

组件格式为 `org.example.vendorhome/org.example.vendorhome.HomeActivity`，这里只是占位格式，不代表实际厂商入口。不要把默认 HOME Intent 用作 Original home 的回退，以免重新进入 Bridge 形成循环。代码也拒绝把原生入口配置到本示例的两个应用包。

若某固件只能通过广播打开菜单，设置 `native_menu_mode` 为 `broadcast`，同时填入实际验证的 Action 和导出 Receiver。该模式要求显式组件，并检查 Receiver 是否可见；需要在 Manifest 的 `queries` 中声明对应厂商包。不要把一个固件上观察到的入口视为 Android 通用接口。

`OwnedKeyPress` 默认拒绝取消事件，并要求 DOWN/UP 的键码及 `downTime` 匹配。兼容开关开启后，只对 MENU 键码 82、虚拟输入设备值 -1、精确 flags 30001 的事件组合放行取消标记。-1 是输入事件 API 的虚拟设备值，不是某台设备的标识。该特例必须在目标固件确认后才启用；应用仍需处于 resumed 且持有窗口焦点。切换窗口、暂停、进入新页面和新 Intent 都会清空未完成按键。

## Bridge 的边界

`boot-bridge/src/main/res/values/config.xml` 可配置目标包与 Activity。普通 HOME 转交必须同时满足 `onResume`、当前焦点和 `hasWindowFocus()`；请求最长等待 3 秒，失焦或暂停立即取消。取消和超时不会在之后的生命周期回调中自动重试。失败后保留恢复界面，由用户选择 Try again 或 System settings，避免不断拉起目标应用。

Bridge 通过只读 `boot_count` 和 `elapsedRealtime` 识别新开机，并先提交本地消费状态再转交。第一次运行只建立基线；计数缺失、回退、相同开机或超过窗口不会触发入场动画。普通 HOME 的入场窗口是 10 分钟。

可选的 `StartupActivity` 用于适配明确支持 INFO 入口的固件，默认 `enable_startup_entry=false`。启用后使用更短的 3 分钟冷启动窗口、最多 8 秒首次焦点等待，并在实际转交时用单调时钟再次检查截止，避免超时回调晚派发造成越界；中断后结束。开启这个组件本身不会建立任何固件启动路由。此入口与 HOME 的计数基线共享，因此同一次开机不会重复消费；若前一个入口已消费但在转交前取消，随后同次 HOME 只打开首页，可能省略开场。

本工程没有无障碍服务、悬浮窗、后台拉起服务、启动广播接收器或全局按键监听；不写系统设置，不修改开机动画，不切换默认 HOME，也不配置固件开机链。是否允许选择第三方默认 HOME、是否调用 INFO 入口，以及特定原生页面能否打开，需要在接收者的目标设备上独立确认。应用入场动画不代表系统 bootanimation 已被替换。

## 可复用的验证重点

纯 Java 测试覆盖失焦清除、孤立 UP、取消键、重复释放、重复 DOWN、MENU 特例默认关闭、短页聚焦、入场回调失效、Bridge 请求过期和冷启动基线。接收者完成构建后，还需要在自己的设备上确认遥控器焦点顺序、返回路径、第三方应用返回、原生页面适配、待机唤醒和 HOME 路由。源代码测试不能证明这些设备行为。
