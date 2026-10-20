# MemeCollector

Windows 和 Android 11+ 的 QQ / 微信表情收集工具，基于 OhMyMeme 定制。主动选择后保存原文件，保留 GIF、动态 WebP，不持续读取全部聊天。

## v0.1.0 下载

[版本发布页](https://github.com/coderirse/meme_sctaping/releases/tag/v0.1.0) · [安卓 APK](https://github.com/coderirse/meme_sctaping/releases/download/v0.1.0/MemeCollector-Android-0.1.0.apk) · [Windows 安装包](https://github.com/coderirse/meme_sctaping/releases/download/v0.1.0/MemeCollector-0.1.0-setup.exe) · [Windows 便携包](https://github.com/coderirse/meme_sctaping/releases/download/v0.1.0/MemeCollector-Windows-0.1.0.zip)

正式版 Android 包名为 `com.shang.memecollector`，测试版为 `com.shang.memecollector.debug`。已在 vivo X100 Ultra / Android 16 上验证 QQ 收集、28 帧 GIF 原文件保存与增量去重；双端加密协议通过 USB TCP 转发完成实机往返验证。Android 11 实机、Wi-Fi 自动发现和手机微信新增收藏的完整往返仍待补测。

完整源码、校验文件和更新说明见发布页及 [v0.1.0 发布说明](docs/releases/v0.1.0.md)。

## 安装与使用

构建产物位于 `dist/`：

- `MemeCollector-0.1.0-setup.exe`：Windows 用户级安装包，无需管理员权限。
- `MemeCollector-Windows-0.1.0.zip`：Windows 便携包，解压后运行 `MemeCollector/MemeCollector.exe`。
- `MemeCollector-Android-0.1.0.apk`：独立包名、独立签名的安卓正式版。
- `MemeCollector-Source-0.1.0.zip`：两端修改后的完整源码及许可证，不包含个人表情、账号数据或签名密钥。
- `SHA256SUMS.json`：构建产物校验值。

### Windows QQ

1. 在 QQ 中收藏喜欢的表情，并打开表情面板让原图加载。
2. 在本工具点击“导入 → 收集 QQ 表情”，选择账号，点击“扫描 QQ 缓存”。
3. 预览、勾选后点击“保存所选”。默认只显示未入库项，可取消勾选“只看未保存”。
4. 点击“打开目录”查看原文件；全局快捷键默认为 `Ctrl+Alt+N`，可在设置修改。

缓存可能包含已取消收藏的表情，所以列表称为“候选”。多账号必须明确选择；自动定位失败时选择 QQ 用户数据目录。

### Windows 微信

1. 保持 Windows 微信登录，打开“添加的表情”面板。
2. 在本工具点击“导入 → 收集微信表情”，选择账号，点击“读取微信表情”。
3. 清单读取完成后，查看预览或保存时才下载对应原文件；勾选保存即可。
4. 若数据目录未找到，选择 `xwechat_files`，也可直接选择账号目录。失败项可主动重试。

微信辅助程序在本机读取表情数据库密钥并解密；密钥不写入采集索引，也不发送给云服务。文件下载使用微信 CDN；操作仍需要网络。微信 3.x 不在此适配范围。

### 安卓 QQ

1. 安装并启动 [Shizuku](https://shizuku.rikka.app/zh-hans/guide/setup/)。Android 11+ 可用开发者选项的无线调试配对；连接电脑时也能通过 ADB 启动。
2. 首次启动 MemeCollector，选择保存位置。推荐通过系统目录选择器选择共享位置，例如 `Pictures/MemeCollector`；默认位置为应用私有目录。
3. 点击“导入 → 从手机 QQ 缓存导入”，授予本工具 Shizuku 权限。
4. 候选列表提供动图预览和选择；默认只看未保存项。点击“导入”保存到表情库，或“转存到…”选择外部文件夹。
5. 保存结果分别显示成功、重复、不支持、超限及失败数量。可取消正在保存的任务；已完成项保留。

手机重启后可能需要重新启动 Shizuku。开启开发者模式不等于 Root；Shizuku 也不能保证读取任意应用的私有目录。权限失效、目录不可访问和空缓存会分别提示。

可在系统快捷设置面板添加 MemeCollector 磁贴，一次点击打开 QQ 收集入口。独立测试版包名带 `.debug`，其授权和数据与正式版分别管理。

### 安卓微信与电脑互传

手机微信中添加喜欢的表情，随后在电脑微信打开表情面板并使用 Windows 端收集。

两端连接同一可信局域网；电脑设置中开启“局域网互联”并设置连接密钥，手机设置中扫描或输入电脑 IP，连接并在电脑确认后，手机点“拉取”。只传输缺失文件，保留原字节和哈希；默认不配置云账号。防火墙阻断时可手动允许程序在专用网络通信。

安卓导入菜单的“微信表情（经电脑）”提供同样的操作说明。手机不能独立提取微信私有表情，电脑需要在线。初次同步需要确认手机添加的表情已在电脑端出现。

## 文件与支持边界

- PNG / JPEG / GIF / WebP 按实际图片内容识别；扩展名错误时自动纠正。
- 普通 GIF、动态 WebP 直接复制原文件，不抽帧、不重编码。缩略图与原文件分开存储。
- Windows 采集默认不解码上游实验性隐写 GIF；安卓普通导入同样默认保留原字节。
- SHA-256 去重；失败不登记为已收集，重复扫描可恢复，单文件失败不影响其他文件。
- 微信商店专用格式、QQ 超级表情和无法解码的文件明确报为不支持，不会只保存首帧伪装成功。
- 默认导入上限为 20 MiB、最长边 2560px。桌面可通过已有设置调整；安卓保持上限以控制内存。
- Windows 配置位于 `%APPDATA%/MemeCollector`，数据库及默认原文件位于 `%LOCALAPPDATA%/MemeCollector`；可在设置更换原文件目录。
- 两端禁用自动升级到上游安装包。定制版通过本项目产物升级。

实际验证范围和待验证项目见 [验证记录](docs/verification.md)。Android 11+ 是最低版本设置，不表示已经逐台验证所有厂商和 QQ / 微信版本。

## 开发与构建

主仓库管理构建脚本、文档和两个组件的固定版本。桌面、安卓子模块均从本仓库获取，分别发布在 `components/desktop`、`components/android` 分支；保留各自上游历史，原始基线见 [upstream-lock.json](upstream-lock.json)。不要直接在上游最新分支上覆盖当前修改。

```powershell
git clone --recurse-submodules https://github.com/coderirse/meme_sctaping.git
cd meme_sctaping
# 已经克隆但缺少组件时：
git submodule update --init --recursive
# 检出本次发布的完整固定版本：
git checkout v0.1.0
git submodule update --init --recursive
```

也可下载发布页的 `MemeCollector-Source-0.1.0.zip`；GitHub 自动生成的 Source code 压缩包不包含子模块源码。

Windows 开发环境：Python 3.12、Node.js/npm；打包还需要 Visual Studio 2022 C++ Build Tools、完整 Windows SDK、CMake、Inno Setup 6。Android 需要 JDK 17+、Android SDK 36。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r apps\desktop\requirements.txt pytest black ruff
Push-Location apps\desktop
npm.cmd ci
npm.cmd run build
..\..\.venv\Scripts\python.exe -m src
Pop-Location
```

```powershell
# Windows：可用 ISCC_DIR 指定 ISCC.exe；未安装 Inno 时使用 --portable-only。
$env:ISCC_DIR = 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
.\.venv\Scripts\python.exe scripts\build.py desktop

# Android：首次构建自动生成本项目的 release 密钥，不需要上游私有仓库。
$env:JAVA_HOME = 'D:\Android-studio_\jbr'
.\.venv\Scripts\python.exe scripts\build.py android

# 仅更新源码归档和校验值。
.\.venv\Scripts\python.exe scripts\build.py source
```

正式版密钥位于 `apps/android/keystore/memecollector-release.jks`，密码配置在 `apps/android/keystore.properties`，两者已忽略。请自行备份以便后续同签名升级；不要提交或分发这两个文件。

可重复验证命令：

```powershell
Push-Location apps\desktop
..\..\.venv\Scripts\python.exe -m pytest tests -q
..\..\.venv\Scripts\python.exe -m black --check src
..\..\.venv\Scripts\python.exe -m ruff check src
Pop-Location
.\.venv\Scripts\python.exe scripts\probe.py --wechat-read
.\.venv\Scripts\python.exe scripts\ui_smoke.py
```

`probe.py` 只输出版本、数量与图片格式等汇总，个人样本在 gitignored 的 `.local/`，不写入发布源码。安卓单元测试由构建脚本执行。设备与桥接验证：

```powershell
.\.venv\Scripts\python.exe scripts\device_test.py
.\.venv\Scripts\python.exe scripts\lan_smoke.py
# 打开正式版的 QQ 候选列表后，验证选一个、保存原字节和增量过滤。
.\.venv\Scripts\python.exe scripts\phone_ui_smoke.py --package com.shang.memecollector
```

`device_test.py` 保留目标应用的安装状态，避免常规 connected test 运行结束卸载应用造成 Shizuku 授权及设置丢失。`lan_smoke.py` 用临时 USB TCP 转发验证实际双端协议和字节保留，不代表已覆盖 Wi-Fi 自动发现。`phone_ui_smoke.py` 会保存实际列表中的一个表情，测试范围限定本项目正式版或测试版。

## 开源声明

本项目按 [GPL-3.0](LICENSE) 分发，保留 OhMyMeme 及其依赖项目的作者和许可证信息。详见 [第三方说明](docs/THIRD_PARTY_NOTICES.md)。
