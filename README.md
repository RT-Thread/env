<p align="center">
  <img src="assets/env.png" alt="RT-Thread Env" width="406">
</p>

# RT-Thread Env

RT-Thread Env 是面向 RT-Thread 开发的工具集，提供项目配置、软件包管理、SDK 配置和插件管理功能，支持命令行与浏览器界面。

- 使用 `menuconfig` 配置 RT-Thread 内核、组件和软件包。
- 使用 `pkgs` 管理项目的软件包，使用 `sdk` 配置开发工具链。
- 使用 `webui` 进行项目构建、SDK 管理、本地工具链配置和插件管理。

Env 2.x 面向 RT-Thread 5.1.0 之后的版本及主开发分支。使用 RT-Thread 5.1.0 或更早版本时，请选择 Env 1.5.x。

## 安装与激活

Env 使用 Python 3 和 Git，默认安装在用户主目录的 `.env` 下。首次激活时会创建独立的 Python 虚拟环境并安装运行依赖，无需在系统 Python 中单独安装 SCons 或 Kconfiglib。

### Linux

以 Ubuntu 为例，下载安装脚本并执行：

```bash
wget https://raw.githubusercontent.com/RT-Thread/env/master/install_ubuntu.sh
chmod +x install_ubuntu.sh
./install_ubuntu.sh
```

如需使用中国大陆镜像，可将下载命令替换为：

```bash
wget https://gitee.com/RT-Thread-Mirror/env/raw/master/install_ubuntu.sh
```

安装完成后，在当前终端激活 Env：

```bash
source ~/.env/env.sh
```

其他系统的安装入口：

| 系统 | 安装脚本 |
| --- | --- |
| Arch Linux | [install_arch.sh](install_arch.sh) |
| openSUSE | [install_suse.sh](install_suse.sh) |
| macOS | [install_macos.sh](install_macos.sh) |

macOS 需先准备 Python 3，安装后同样使用 `source ~/.env/env.sh` 激活。

### Windows

在 PowerShell 中下载安装脚本并执行：

```powershell
Invoke-WebRequest https://raw.githubusercontent.com/RT-Thread/env/master/install_windows.ps1 -OutFile install_windows.ps1
.\install_windows.ps1
```

如脚本被执行策略阻止，请按本机或组织的安全要求配置执行策略。安装 Python 或 Git 时可能需要管理员权限；安装完成后，日常使用无需以管理员身份运行。

在当前 PowerShell 会话中激活 Env：

```powershell
. "$HOME\.env\env.ps1"
```

每次打开新终端后均需激活 Env。也可以将激活命令加入 shell 启动配置或 PowerShell 的 `$PROFILE`。

## 配置与构建项目

先激活 Env，再进入目标 BSP 根目录。该目录应包含 `Kconfig` 和项目构建文件：

```bash
cd /path/to/rt-thread/bsp/your-board
menuconfig
pkgs --update
scons
```

`menuconfig` 使用 Python 终端配置界面，保存项目的 `.config` 并生成配置头文件，默认文件名为 `rtconfig.h`。`pkgs --update` 根据配置安装或移除软件包，`scons` 执行项目构建。

构建前需准备与目标芯片匹配的工具链，并按 BSP 要求配置编译器路径。

常用配置选项：

| 命令 | 用途 |
| --- | --- |
| `menuconfig --config saved.config` | 使用指定配置文件进行配置 |
| `menuconfig --silent` | 无交互地加载现有配置，应用默认值和依赖关系并保存 |
| `menuconfig --generate` | 从现有 `.config` 生成配置头文件 |
| `menuconfig --setting` | 配置 Env 的自动更新软件包等选项 |

## 软件包与 SDK

在 `menuconfig` 中选择项目所需的软件包后，使用以下命令管理：

| 命令 | 用途 |
| --- | --- |
| `pkgs --update` | 按当前项目配置更新软件包 |
| `pkgs --list` | 查看当前配置选中的软件包 |
| `pkgs --upgrade` | 更新本地软件包索引 |

软件包索引更新后，可重新运行 `menuconfig` 选择新增的软件包或版本。

通过终端界面选择和安装 SDK：

```bash
sdk
```

SDK 也可在 WebUI 的设置页面中管理。已有工具链可在“本地工具链配置”中登记，实际编译器选择仍以项目配置为准。

## WebUI

在项目目录运行以下命令，启动服务并打开浏览器：

```bash
webui
```

服务默认仅监听本机地址。浏览器未自动打开时，请访问终端输出的 `Launch URL`；使用 `webui --no-browser` 可仅启动服务。

WebUI 提供项目首页、插件中心和设置页面。项目构建需要工作区具备相应构建文件；浏览器中的 BSP Kconfig 编辑功能由独立插件提供。

按 `Ctrl+W` 可无确认退出 WebUI，并停止对应服务。刷新页面或切换标签页不会主动退出服务。也可以在启动服务的终端按 `Ctrl+C` 退出，或使用页面中的“退出 WebUI”按钮。

需要后台运行时，使用以下命令：

```bash
webui start
webui status
webui stop
```

## 插件

插件用于扩展 Env 命令或 WebUI 页面。激活 Env 后，可以安装本地 `.epack` 插件包并查看已安装插件：

```bash
rt-env plugin install /path/to/plugin.epack
rt-env plugin list
```

安装前请核对插件来源和所需权限。插件的升级、卸载、诊断及开发说明见 [插件文档](plugins/README.zh-CN.md)。

## 帮助与参考

查看命令帮助及当前环境信息：

```bash
rt-env --help
rt-env --info
menuconfig --help
pkgs --help
webui --help
```

- [插件使用与开发](plugins/README.zh-CN.md)
- [EBuild 构建框架](ebuild/README.md)
- [插件包格式规范](plugins/spec/README.md)
