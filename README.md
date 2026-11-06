# Android TV Launcher Kit

可复用的Android TV桌面工程、诊断方法和Agent Skill。覆盖冷启动、遥控待机、HOME路由、按键重复、原生共存、品牌开场、性能测量及恢复。示例使用中性名称和通用几何图形，没有任何特定用户、公司或设备绑定。

它是适配起点，**不是通用刷机包**。示例不替换系统开机动画，不保证固件允许第三方默认HOME；厂商特殊按键与启动行为默认保守处理。

## 入口

| 需要 | 文件 |
|---|---|
| 让Agent按完整方法开展新任务 | [SKILL.md](skills/android-tv-launcher/SKILL.md) |
| 新建Android应用 | [project/README.md](project/README.md) |
| 开机/唤醒/默认桌面分析 | [启动手册](skills/android-tv-launcher/references/startup-and-standby.md) |
| 按键/抢屏/返回问题 | [输入与共存](skills/android-tv-launcher/references/input-and-coexistence.md) |
| 视觉和帧率问题 | [渲染与导航](skills/android-tv-launcher/references/rendering-and-navigation.md) |
| 设置修改与撤回 | [运维手册](skills/android-tv-launcher/references/operations.md) |
| 验收范围和记录模板 | [验证方法](skills/android-tv-launcher/references/verification.md) |
| 旧方案为何失败、如何选择 | [取舍记录](skills/android-tv-launcher/references/decision-history.md) |
| 分享隐私边界 | [PRIVACY.md](PRIVACY.md) |

## 使用Skill

将`skills/android-tv-launcher`复制到当前Agent的Skill目录（Codex通常是用户目录下的`.codex/skills`，或CODEX_HOME指向的位置），重新加载Skill后调用：

```text
使用 $android-tv-launcher 排查这台电视的开机和遥控器问题。
保留原生应用，只修改已经明确授权的部分，并给出真实验收结果。
```

Skill可独立搬走；所需参考、运维脚本和通用工程都包含在该文件夹。工程副本与根目录`project/`相同，脚本副本与`tools/tvctl.py`相同，打包器会核对一致性。Skill不会自动连接设备或安装应用。

## 先离线查看运维计划

运维、审计和打包脚本使用 Python 3.10 或更新版本及标准库。

在完整包根目录运行：

```sh
python3 tools/tvctl.py snapshot --serial DEVICE
python3 tools/tvctl.py standby-preserve --serial DEVICE --vendor-profile xiaomi
```

以上不会调用ADB。只有显式`--inspect`或`--apply`才访问设备；PRIVATE_DIR、DEVICE等占位值需自行替换，私有状态目录必须放在分享包以外。厂商适配要先核对本机证据，操作说明见运维手册。

## 验证及再次打包

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 python3 project/tools/test-logic.py
PYTHONDONTWRITEBYTECODE=1 python3 tools/audit_share.py .
PYTHONDONTWRITEBYTECODE=1 python3 tools/package_release.py --output ../android-tv-launcher-kit.zip
```

私有词补充列表可用`--denylist-file`传入，必须放包外。打包拒绝覆盖已有输出，默认不包括编译产物；需要更新时使用新的版本和文件名。重新开发后的构建输出、私有资料或缓存会令审计失败，应留在工作副本或包外。

本次验证的实际范围见[VERIFICATION.md](VERIFICATION.md)。产物完整性见`MANIFEST.sha256`，不含真实设备身份摘要。软件与第三方权利范围见[NOTICE.md](NOTICE.md)。
