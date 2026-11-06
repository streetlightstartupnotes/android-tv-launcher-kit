# 运维、部署与恢复

`scripts/tvctl.py`是Skill中的独立脚本；完整项目包里的相同文件位于`tools/tvctl.py`。使用Python标准库，无网络下载、无自动发现设备、无自动ADB连接。命令中的`DEVICE`、`PRIVATE_DIR`、`PACKAGE`等均需替换；PRIVATE_DIR必须是分享包/Skill以外的私人目录。

## 三种模式

| 模式 | 行为 |
|---|---|
| 不加模式参数 | 离线JSON计划，零ADB调用 |
| `--inspect` | 显式连接标识的设备，只读所需状态 |
| `--apply` | 备份、身份核对、有限写入、回读与阶段报告 |

`snapshot`只提供离线计划或inspect。所有inspect/apply都要求显式`--state-dir`；设备身份只保留摘要，serial/IP、原始日志和整份dumpsys不会进入分享树。私有报告仍应当作设备资料，不再次打进公共包。

```sh
python3 scripts/tvctl.py snapshot --serial DEVICE
python3 scripts/tvctl.py snapshot --serial DEVICE --state-dir PRIVATE_DIR --inspect
```

先核对当前设备是否就是要修改的那台。后来恢复时匹配同一设备摘要；不能把刚读到某台电视的摘要当作旧备份归属的证明。

## 厂商第三方启动项

```sh
python3 scripts/tvctl.py set-startup --serial DEVICE --package PACKAGE --vendor-profile xiaomi
python3 scripts/tvctl.py set-startup --serial DEVICE --package PACKAGE --vendor-profile xiaomi --state-dir PRIVATE_DIR --inspect
python3 scripts/tvctl.py set-startup --serial DEVICE --package PACKAGE --vendor-profile xiaomi --state-dir PRIVATE_DIR --apply
```

PACKAGE应为已安装、入口已检查的启动桥接，而不是盲目填写示例包。厂商设置可能缓存目标，恢复公开键不一定清除私有缓存。设置读回不是冷启动成功；必须重启验收。

## 待机保留前台

先按[startup-and-standby.md](startup-and-standby.md)核对本机确实存在相同调用链和设置分支，再执行：

```sh
python3 scripts/tvctl.py standby-preserve --serial DEVICE --vendor-profile xiaomi
python3 scripts/tvctl.py standby-preserve --serial DEVICE --vendor-profile xiaomi --evidence-confirmed --state-dir PRIVATE_DIR --apply
```

`--evidence-confirmed`记录调用者已完成适配判断，不是自动检测器。修改作用于该系统待机策略：保留所有应用的睡前前台，不仅是示例桌面；需要分别测试自有与原生页面的睡/醒。

## 撤下自己的旧按键过滤服务

```sh
python3 scripts/tvctl.py retire-guard --serial DEVICE --component PACKAGE/CLASS
python3 scripts/tvctl.py retire-guard --serial DEVICE --component PACKAGE/CLASS --state-dir PRIVATE_DIR --apply
```

仅移除调用者明确给出的组件，保留其他无障碍服务和全局开关。随后回读绑定与InputFilter，再让用户在原生页面试实体方向键。不要为恢复UI自动重绑旧过滤器。

## 回滚

写入前创建独立备份与阶段报告，不覆盖旧备份。保存“原键不存在”和“空字符串”的区别。多步骤操作失败停止后续动作，不谎称是原子事务。

```sh
python3 scripts/tvctl.py restore --serial DEVICE --backup PRIVATE_BACKUP
python3 scripts/tvctl.py restore --serial DEVICE --backup PRIVATE_BACKUP --state-dir PRIVATE_DIR --apply
```

恢复先检查设备摘要与备份结构，只有当前值仍等于本轮写入值才还原。用户后来改成其他值时保留；原值缺失则删除该键。写后读取实际值，不因命令退出码为零就算成功。恢复脚本不删除应用数据，不切换页面，不发送电源键。

## 应用构建和安装是另外的步骤

工程构建见`assets/project/README.md`。在新工作目录里选自己的包名和品牌资源，使用自己的签名。不要把示例标识当作生产签名/包名，也不要尝试用它覆盖其他签名的已装应用。

APK版本与产物不可混写：记录源码版本、构建参数、APK校验与签名验证，保留可恢复的旧版本；修改后提升版本，不覆盖已有同名产物。安装、启动Activity、改默认HOME、改启动项、改屏保/无障碍是不同动作，按当前授权分别执行和记录。此运维脚本有意不自动安装、重启或拉前台。

测试时电视重启可能关闭网络ADB；区分网络不可达、端口关闭、设备offline和电脑客户端故障。调试失联不等于应用没有启动，也不要把重新手动启动后的首页算成自动开机结果。
