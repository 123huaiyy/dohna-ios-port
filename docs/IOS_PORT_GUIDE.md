# 多娜多娜 (Dohna Dohna ver1.1 中文版) iOS 移植方案与构建指南

## 一、方案选型结论：为什么不用静态重编译 `dohnadohna.exe`

对原版《多娜多娜 ver1.1》（中文汉化版）游戏目录的实测分析结论如下：

1. **原程序架构本质**：
   - `dohnadohna.exe` 与 `dohnadohna.exe.org` 均为 32 位 x86 PE 可执行文件（`3,975,424` 字节，stripped 节名），本质上是 AliceSoft **System 4.3 (AIN v14)** 引擎壳（导入 `d3d11.dll`、`WINMM.dll`、`WININET.dll` 等；当前 `dohnadohna.exe` 将 `user32.dll` 导入表替换为了汉化外挂钩子 `Mai@KF.dll`）。
   - 游戏全部脚本、对话、UI 状态机与 HLL 调用表都在字节码文件 `dohnadohna.ain` 中（zlib 压缩 `3,208,015` 字节，解压后 `20,695,512` 字节，`VERS = 14`、`GVER = 100`、`57,532` 条 `MSG1` 消息、`38,310` 条 `STR0` 字符串、`36` 个 HLL 库，含 `PartsEngine` 868 个函数与 `SealEngine` 248 个函数）。
   - 直接解码 `dohnadohna.ain` 中的 `MSG1`/`STR0` 后可确认：**中文文本（CP936 / GBK）已直接内嵌于 `dohnadohna.ain` 中**，无需移植或模拟 Win32 钩子 `Mai@KF.dll`。
   - 对 4 个 `.afa` 归档实测解压头校验均通过标准 AFAv2 格式。

2. **静态重编译的局限**：
   - 对 `dohnadohna.exe` 做 x86→ARM64 静态重编译（类似 Sleigh/RetDec 转译）需要额外重实现整套 Win32 API、Direct3D 11、DirectSound 与 Windows 窗口消息泵，工作量远高于重用字节码虚拟机。

3. **最终选用方案（开源 System 4.3 VM + Aether iOS 宿主壳）**：
   - **VM 与渲染核**：采用支持《多娜多娜》AIN v14、`SealEngine` 3D 战斗渲染、`PartsEngine` v14 与 GBK/GB18030 中文字符规则的开源分支 **`USADA-KARROT/xsystem4`**（commit `8188c70`）+ **`USADA-KARROT/libsys4`**（commit `247f544`）。
   - **iOS 宿主壳**：复用 **`AetherKiri/Aether`**（Godot 4.7 iOS 16+ 宿主工程），通过其 `bridge/xsystem4_runtime` 接口在 ARM64 真机上提供 EAGL OpenGL ES 3.0 离屏帧缓冲、iOS 文件导入器（Files App）、虚拟按键与音频中断管理。
   - **JIT 与 Shader 检查**：确认 `xsystem4` 不依赖 `ffi_prep_closure` 动态 JIT 代码生成（仅用 `ffi_prep_cif` + `ffi_call`），`shaders/` 目录下递归全部 51 个 `.glsl` 着色器也均不含桌面 GLSL 1.x 旧关键字，可直接运行于未越狱 iOS OpenGL ES 3.0 设备。

---

## 二、在本项目 `dohna_ios_port` 中已完成的引擎与工程适配

原版游戏目录 **全程保持只读未修改**。所有工程改写均位于本仓库目录：

1. **Aether 宿主接入层 (`engine/xsystem4/include/embedded.h`, `src/embedded.c`)**：
   - 接入 `xsystem4_host_run` / `checkpoint` / `framebuffer` / `present` / `poll_event` / `mouse_position` / `text_input` 回调。
   - **修复 v14 分辨率与中文编码初始化**：`AliceStart.ini` 未显式填写 `ViewWidth`/`ViewHeight`；`src/embedded.c` 已同步 `system4.c` 逻辑，检测到 AIN v14 `PartsEngine.SeekMessage` 时自动将默认分辨率设为 **`1280x720`**，并执行 `gbk_string_rules_enable()` / `gb18030_detect_strings()`，避免中文乱码或窗口尺寸错乱（800x600）。
2. **iOS SDK 与沙盒兼容补丁**：
   - `src/hll/system.c`：`OpenWeb` 在 iOS/嵌入式环境禁用 `system("open ...")`（iOS SDK 编译禁止 `system()`）。
   - `src/screenshot.c`：在 iOS/嵌入式下禁用 `popen("zenity ...")`。
   - `src/movie_ffmpeg.c`：将 APEG `SOND` 临时音频路径从只读的 `/tmp/` 改为优先读取 iOS 沙盒 `$TMPDIR` 或 `config.save_dir`。
   - `src/hll/vmDialog.c` 与 `src/vm.c`：拦截主线程之外的 `SDL_ShowSimpleMessageBox` / `SDL_ShowMessageBox` 弹窗以及 `signal()` 覆盖，增加 `vm_execute` / `vm_sleep` 宿主检查点。
3. **OpenGL ES 3.0 / Apple 头文件修复**：
   - `include/gfx/gl.h`：在 Apple + `USE_GLES` 下包含 `<OpenGLES/ES3/gl.h>`。
   - `include/gfx/gfx.h` & `src/video.c`：将 `vertex_pos` / `vertex_uv` 改为有符号 `GLint`，并在 `gfx_run_job` 中补充 `>= 0` 保护，防止移动端 GLES3 编译优化掉未使用属性返回 `-1` 时崩溃。
4. **可重复启动与全子系统清理 (`_fini` / `_ModuleFini` / `PE_Reset`)**：
   - 已在 `video.c`, `input.c`, `audio.c`, `audio_meta.c`, `audio_mixer.c`, `effect.c`, `scene.c`, `sprite.c`, `font_fnl.c`, `font_freetype.c`, `text.c`, `asset_manager.c`, `ffi.c`, `hacks.c`, `parts/parts.c`, `parts/render.c`, `hll/SACT2.c`, `hll/MsgSkip.c`, `hll/SealEngine.c`, `hll/AnteaterADVEngine.c`, `hll/InputString.c`, `hll/PlayMovie.c`, `hll/DrawMovie.c`, `hll/FillAngle.c` 补齐会话退出时的资源释放与静态状态复位。
5. **修复 Aether CMake 脚本对 `USADA-KARROT/libsys4` 的两处破坏性替换 (`aether_overlay/CMakeLists.xsystem4_runtime.txt`)**：
   - **修复 `_exit(code);` 误替换**：原版 `Aether` 用 `string(REPLACE "exit(code);" ...)` 会把 `USADA-KARROT/libsys4/src/system.c` 中的 `_exit(code);` 误改写成 `_xsystem4_host_exit(code);` 导致链接失败；覆盖版先匹配 `_exit(code);` 再回退 `exit(code);`。
   - **修复 `afa.c` 解压模式匹配**：原版 `Aether` 只匹配 `zlib_decompress_exact(...)`，`USADA-KARROT/libsys4` 已改为标准 `uncompress(...) != Z_OK`；覆盖版同时兼容两种写法，并显式链接 `ZLIB::ZLIB`。

---

## 三、目录结构与交付文件

- `engine/xsystem4/`：已应用上述全部补丁的 `USADA-KARROT/xsystem4` + `libsys4` 源码。
- `aether_overlay/CMakeLists.xsystem4_runtime.txt`：替换 `Aether/bridge/xsystem4_runtime/CMakeLists.txt` 的构建定义，补全 `zlib.c`、`OpenGLES` 与 `iconv` 链接。
- `aether_overlay/apply_dohna_standalone.py`：构建前将 Aether 壳层打包为独立《多娜多娜》应用（修改 `CFBundleDisplayName` / 包 ID，跳过协议弹窗与多游戏主界面，开机自动扫描 `user://`、`user://<子目录>`、`user://Games/<子目录>` 并直接进入《多娜多娜》，同时自动同步 `SaveData` 与 `User/` 自定义人物）。
- `scripts/build_dohna_ios.sh`：macOS 本地打包脚本，自动拉取 `AetherKiri/Aether`、覆盖运行时与独立应用补丁并构建无签名 `DohnaDohna-Release-Unsigned.ipa`。
- `.github/workflows/build_dohna_ios.yml`：无 Mac 电脑时的 GitHub Actions 云打包工作流（默认 `macos-26`）。
- `scripts/prepare_game_for_ios.ps1`：Windows 游戏数据包精简整理脚本（只复制运行时必需文件，可选带入存档与 `User` 捏人，剔除 `.exe`/`.dll`/修改器与备份文件）。

---

## 四、构建独立版《多娜多娜》`.ipa`（需要 macOS + Xcode 环境）

> **环境边界说明**：当前开发主机为 Windows，不具备 Apple `iphoneos.sdk`、`ld64` 与 Xcode 工具链，因此**无法在 Windows 本地直接链接 ARM64 Mach-O 二进制并生成 `.ipa`**。下面提供两种真实构建方式：

### 方式 A：没有 Mac —— 使用 GitHub Actions 云端打包（推荐）

1. 将本仓库推送到你的 GitHub 仓库（注意不要提交任何游戏本体资源文件）。
2. 打开仓库的 **Actions** -> 选择 **Build Dohna Dohna iOS IPA** -> 点击 **Run workflow**（`build_type` 选 `release`，`runner` 默认 `macos-26`）。
3. 构建完成后，在 Workflow Run 页面底部的 Artifacts 下载 **`dohna-standalone-ios-release-unsigned-ipa`**（内含 `DohnaDohna-Release-Unsigned.ipa`）。

### 方式 B：有 Mac —— 本地直接编译

在 macOS 上安装 Xcode、Homebrew 依赖（`cmake ninja pkgconf autoconf automake autoconf-archive libtool gettext coreutils bison nasm ccache mono`）、Godot 4.7.2-stable 及其 `ios.zip` 导出模板后执行：

```bash
cd /path/to/dohna_ios_port
chmod +x scripts/build_dohna_ios.sh
./scripts/build_dohna_ios.sh
```

生成的独立版安装包路径位于：`.aether/out/godot/ios/release/DohnaDohna-Release-Unsigned.ipa`。

---

## 五、整理手机端游戏数据与侧载运行

### 1. 在 Windows 整理游戏数据包（瘦身至 ~3.36 GB，只读提取）

在 PowerShell 运行：

```powershell
# 预览将提取的文件清单
.\scripts\prepare_game_for_ios.ps1 -SourceDir "<path-to-DohnaDohna-v1.1>" -IncludeSaveData -IncludeUserCharacters -DryRun

# 正式输出到 .\ios_game_payload\DohnaDohna（同时带入全CG存档与附件 User 捏人）
.\scripts\prepare_game_for_ios.ps1 -SourceDir "<path-to-DohnaDohna-v1.1>" -IncludeSaveData -IncludeUserCharacters
```

脚本仅复制以下 9 个运行时必需文件、生成 `.xsys4rc`（`encoding = "gbk"`）并同步存档/自定义人物到 `SaveData` 与 `savedata\xsystem4\<游戏ID>`，不复制 `.exe`、`Mai@KF.dll`、修改器及备份目录：
- `AliceStart.ini`、`dohnadohna.ain`、`dohnadohnaCG.afa`、`dohnadohnaPact.afa`、`dohnadohnaSound.afa`、`dohnadohnaVoice.afa`、`dohnadohnaEx.ex`
- `Data\Shader.slk`
- `Movie\Op.apeg`
- `.xsys4rc`、`SaveData\`、`savedata\xsystem4\<游戏ID>\`（自动生成/带入）

### 2. 侧载到 iPhone / iPad

1. 使用 **Sideloadly** / **AltStore** / **SideStore**（免费 Apple ID 7 天重签，或开发者证书 / **TrollStore** 永久安装）将 `DohnaDohna-Release-Unsigned.ipa` 安装到 iOS 设备（安装后桌面图标名称直接显示为 **多娜多娜**）。
2. 将 Windows 生成的 `DohnaDohna` 文件夹直接复制到 iPhone **「文件」->「我的 iPhone」->「多娜多娜」**（或通过电脑爱思助手/iTunes 文件共享导入该 App 根目录）。
3. 打开 **多娜多娜** App，程序会自动跳过原管理界面并直接启动游戏；如果尚未放入文件，则会提示放置位置并提供「重新检测并启动」按钮。

---

## 六、已知上游引擎特性与限制

- 根据 `engine/xsystem4/docs/checkpoints/2026-09-28/` 上游开发文档：`USADA-KARROT/xsystem4` (`wip/post-checkpoint-2026-07-06`) 已可运行启动、`Op.apeg` 片头、ADV 对话、据点（Azito）、3D 迷宫/战斗及存档读档 / `ResumeLoad`，但部分复杂长流程与诸如返回标题 `system.Reset` 等边界仍在持续完善中；遇到特定界面报错或卡死时建议配合即时存档（ResumeSave）推进。
