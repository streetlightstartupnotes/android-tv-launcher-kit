---
name: android-tv-launcher
description: 设计、排查和实现与原生应用共存的 Android TV 桌面，处理冷启动、遥控待机、HOME 路由、按键重复与动效性能，并交付可恢复配置。用于电视桌面定制和相关兼容故障，不把应用开场等同系统刷机。
---

# Android TV Launcher

以目标电视的实际行为为准，交付可验证的桌面体验及恢复办法。内附无品牌、无设备绑定的双模块示例工程；它是需适配的起点，不是所有电视通刷包。

## 先确定问题在哪一层

把用户说的“开机”还原成最近一次实际操作：断电重上电、系统重启、遥控器短按关/开、退出屏保、普通HOME。记录每种操作期望恢复哪个页面。读取boot_count、uptime、电源状态、前台组件和应用停止状态，不凭单次成功合并不同路径。

按需读取：

- 开机、HOME、启动动画或待机问题：[startup-and-standby.md](references/startup-and-standby.md)。
- 抢屏、按键多跳、MENU失效、返回层级：[input-and-coexistence.md](references/input-and-coexistence.md)。
- 品牌效果、粒子、卡顿与页面动效：[rendering-and-navigation.md](references/rendering-and-navigation.md)。
- 修改目标设备、移除旧集成、回滚：[operations.md](references/operations.md)。
- 交付与验收：[verification.md](references/verification.md)。
- 判断旧方案取舍及避免重复失败：[decision-history.md](references/decision-history.md)。

## 实施边界

使用当前任务授权，具体确认缺失的设备和目标，不反复询问已授权的常规步骤。设备地址和应用包名由当前用户提供；此Skill不携带任何已授权设备、品牌素材、签名或历史备份。

原生播放、HDMI、设置、投屏需要共存时，让桌面只处理自己的前台窗口。普通应用切换、包更新和迟到广播不构成回桌面的理由。不要以窗口轮询或延迟启动补偿HOME失败；每次前台转交需要明确来源、实际焦点和取消条件。

MENU取消标记例外、厂商启动键、待机白名单开关只属于经证据确认的固件适配。复制一个设置名或看到命令返回Success，不能当作功能支持。需要时查目标固件本地行为或官方资料，再决定是否采用。

固件刷写、root、签名替换和停用系统桌面不是本Skill的默认执行路径。若应用层达不到用户目标，先明确权限和行为缺口；不要为了演示成功悄悄牺牲原生入口。

## 可用材料

- `assets/project/`：独立Android示例工程，包含桌面、屏保预览、分页导航、应用内开场及独立启动桥接；素材为通用占位图形。复制到新的工作目录后替换包名与自有素材，构建条件见工程README。
- `scripts/tvctl.py`：标准库运维助手。默认完全离线计划，`--inspect`才只读设备，`--apply`才写。私有状态目录必须在Skill/分享工程之外。具体命令见[operations.md](references/operations.md)。

先做最小可复现实验：只改一个有证据的原因，回读实际状态，再重复原触发操作，同时检查原生页面没有被抢走。完整重启和遥控待机分别验收。测试期间有人使用时记录干扰，重新取得明确测试窗口后再下结论。

交付时写清实现、实际验证、用户确认和未完成项。保留失败及撤回原因；不要声称“所有bug清零”，不要把本机演示或本地帧率当成目标电视证据。可复用版本应按[privacy-and-sharing.md](references/privacy-and-sharing.md)重新构建分享树。
