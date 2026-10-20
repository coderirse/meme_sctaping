# 来源与许可证

MemeCollector 是 OhMyMeme 的修改版，并非上游官方发布的软件。

| 组件 | 来源 | 固定提交 / 用途 | 许可证 |
| --- | --- | --- | --- |
| Windows 应用 | https://github.com/OhMyMeme/OhMyMeme | ee7e38b8028954a6454f03df2f7e0ba7b8f88fe7 | GPL-3.0 |
| Android 应用 | https://github.com/OhMyMeme/OhMyMeme-Android | f0a4a72e6cbde8cf732919a2137783b14263cb38 | GPL-3.0 |
| QQNT 提取代码 | https://github.com/VanillaNahida/QQFavoriteExtract | 通过桌面上游集成；保留 qqnt_extract.py 原始声明 | GPL-3.0 |
| Shizuku 客户端 | https://github.com/RikkaApps/Shizuku-API | Android 上游已有 Maven 依赖 13.1.5 | MIT |

本次新增：Windows 候选选择、惰性下载、增量索引、严格格式校验和失败清理；Android 新增过滤与预览、结果分类、权限引导、有界读取、独立签名；双端本地默认值和定制版更新行为；构建脚本与测试。

上游 README、许可证及原始署名均随源码保留。上游已有第三方依赖继续按其各自许可证分发；本项目未复制或分发 QQ、微信客户端代码。WeKit 仅作为调研参考，没有引入其源码或模块。Inno Setup 是本机构建工具，不包含在源码归档中。

`dist/MemeCollector-Source-0.1.0.zip` 包含本次分发版本的修改后源码；构建依赖见各应用的 requirements/package lock/Gradle version catalog。
