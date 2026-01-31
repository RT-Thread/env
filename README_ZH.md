<div align="center">

# RT-Thread Env Python 脚本

[![License: GPL-2.0](https://img.shields.io/badge/License-GPL--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.6+-green.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)]()

**[English](README.md) | 简体中文**

</div>

---

## ⚠️ 版本兼容性提示

| RT-Thread 版本 | 推荐使用 Env 版本 |
|----------------|-------------------|
| **> v5.1.0** 或 **master 分支** | ✅ **env v2.0** (当前版本) |
| **≤ v5.1.0** | ⚠️ [env v1.5.x](https://github.com/RT-Thread/env/tree/v1.5.x) (Linux) / [env-windows v1.5.2](https://github.com/RT-Thread/env-windows/tree/v1.5.2) (Windows) |

### 🔄 v2.0 主要变更

- ✨ **Python 版本升级**：从 Python 2 升级到 Python 3
- 🔧 **配置系统重构**：使用 Python kconfiglib 替代 kconfig-frontends
- 📦 **依赖管理优化**：安装程序自动处理 kconfiglib 依赖

> **注意**：env v2.0 与 env v1.5.x 的 kconfiglib 不兼容。如需切换版本，请先运行 `pip uninstall kconfiglib`。

---

## 📚 目录

- [🚀 快速开始](#-快速开始)
  - [Windows 安装](#windows-安装)
  - [Linux/macOS 安装](#linuxmacos-安装)
- [⚙️ 安装脚本参数](#️-安装脚本参数)
- [💡 使用指南](#-使用指南)
- [❓ 常见问题](#-常见问题)
- [📖 相关资源](#-相关资源)

---

## 🚀 快速开始

### Windows 安装

#### 前置要求

| 项目 | 要求 |
|------|------|
| **权限** | 📋 首次安装需**管理员权限**（设置执行策略和长路径支持）<br>后续更新可使用普通用户权限 |
| **PowerShell** | ✅ Windows PowerShell v5.1+<br>✅ PowerShell 7+ |

#### 编码兼容性说明

> ⚠️ **重要提示**
>
> | PowerShell 版本 | 编码支持 | 说明 |
> |----------------|----------|------|
> | Windows PowerShell (v5.1) | ⚠️ GB2312 默认，需 UTF-8 with BOM | 中文系统需特殊处理 |
> | PowerShell 7+ | ✅ 原生 UTF-8 | 无编码问题 |
>
> 安装脚本已配置为 UTF-8 with BOM 编码，确保兼容性。

#### 安装命令

<details>
<summary><b>🌐 国际用户（官方源）</b></summary>

```powershell
Set-ExecutionPolicy -ExecutionPolicy Bypass Process; irm https://raw.githubusercontent.com/RT-Thread/env/master/tools/install.ps1 | Out-File -Encoding utf8 .\install.ps1; .\install.ps1; Remove-Item .\install.ps1
```

</details>

<details>
<summary><b>🇨🇳 中国大陆用户（镜像源）</b></summary>

```powershell
Set-ExecutionPolicy -ExecutionPolicy Bypass Process; irm https://gitee.com/RT-Thread-Mirror/env/raw/master/tools/install.ps1 | Out-File -Encoding utf8 .\install.ps1; .\install.ps1; Remove-Item .\install.ps1
```

</details>

#### 注意事项

> 💡 **提示**：安装脚本会根据地理位置自动选择镜像源。如需明确指定，请使用 `--cn` 或 `--official` 参数。详见 [安装脚本参数](#️-安装脚本参数)。

> ⚠️ **重要**：
> - ✅ 首次安装需管理员权限设置执行策略和长路径支持
> - 🦠 杀毒软件可能会阻止安装，如有需要请暂时禁用

#### 激活环境

安装完成后，需要激活环境变量才能使用。

<details>
<summary><b>🔧 方案 A：手动激活（临时）</b></summary>

每次启动新的 PowerShell 会话时运行：

```powershell
. ~/.rt-env/env.ps1
```

</details>

<details>
<summary><b>⭐ 方案 B：自动激活（推荐）</b></summary>

将激活命令添加到 PowerShell 配置文件：

```powershell
# 打开配置文件（如不存在则创建）
notepad $PROFILE

# 添加以下行：
. ~/.rt-env/env.ps1
```

**配置文件路径：**

| PowerShell 版本 | 配置文件路径 |
|----------------|-------------|
| Windows PowerShell (v5.1) | `C:\Users\<用户名>\Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1` |
| PowerShell 7+ | `C:\Users\<用户名>\Documents\PowerShell\Microsoft.PowerShell_profile.ps1` |

添加后，每次打开 PowerShell 会自动激活环境。

</details>

### Linux/macOS 安装

#### 安装命令

<details>
<summary><b>🌐 国际用户（官方源）</b></summary>

```bash
bash -c "$(wget https://raw.githubusercontent.com/RT-Thread/env/master/tools/install.sh -O -)"
```

</details>

<details>
<summary><b>🇨🇳 中国大陆用户（镜像源）</b></summary>

```bash
bash -c "$(wget https://gitee.com/RT-Thread-Mirror/env/raw/master/tools/install.sh -O -)" -- --cn
```

</details>

#### 注意事项

> 💡 **提示**：
> - 安装脚本会根据地理位置自动选择镜像源
> - Linux 系统会自动使用 `sudo` 提权安装依赖，无需手动以 root 运行
> - 支持普通用户权限安装，脚本会自动处理权限提升

#### 激活环境

<details>
<summary><b>🔧 方案 A：手动激活（临时）</b></summary>

每次打开新终端时运行：

```bash
source ~/.rt-env/env.sh
```

</details>

<details>
<summary><b>⭐ 方案 B：自动激活（推荐）</b></summary>

将激活命令添加到 shell 配置文件：

```bash
# 对于 bash
echo 'source ~/.rt-env/env.sh' >> ~/.bashrc

# 对于 zsh
echo 'source ~/.rt-env/env.sh' >> ~/.zshrc
```

添加后，每次登录系统时自动激活环境。

</details>

#### 📚 相关教程

- [在 Ubuntu 中安装 Env 并配合 QEMU 模拟器使用](https://github.com/RT-Thread/rt-thread/blob/master/documentation/quick-start/quick_start_qemu/quick_start_qemu_linux.md)

---

## ⚙️ 安装脚本参数

| 参数 | 描述 |
|------|------|
| **基础参数**||
| `-y`, `--yes`, `--auto` | 自动安装，无交互 |
| `-h`, `--help` | 显示帮助信息 |
|**源设置**||
| `-c`, `--cn`, `--gitee` | 使用中国镜像源（Gitee、PyPI TUNA） |
| `-o`, `--official` | 强制使用官方源 |
| **仓库配置**||
| `-P`, `--packages <repo>[#<branch>]` | 指定 packages 仓库地址和分支 |
| `-E`, `--env <repo>[#<branch>]` | 指定 env 仓库地址和分支 |
| `-S`, `--sdk <repo>[#<branch>]` | 指定 sdk 仓库地址和分支 |
| `-t`, `--touch-env-url <url>` | 指定 touch_env.py 下载 URL |
|**路径与安装**||
| `-r`, `--env-root <path>` | 设置自定义 .rt-env 目录路径（默认：`~/.rt-env`） |
| `-p`, `--python [path]` | 安装便携式 Python，安装目录为 path（仅 Windows，默认：D:\Tools\Python） |
|**其他选项**||
| `-d`, `--pyocd` | 安装 pyocd（用于调试） |
| `-e`, `--en`, `--english` | 强制英文显示 |
| `-z`, `--zh`, `--chinese` | 强制中文显示 |
| `-b`, `--backup <strategy>` | 备份策略 |

### 备份策略

| 策略 | 说明 |
|------|------|
| **preserve** (默认) | 保留配置文件（.config）和工具链（local_pkgs），删除其他内容 |
| **delete_all** | 备份后删除现有 ENV 目录 |
| **delete_all_now** | 立即删除现有 ENV 目录，不备份 |
| **backup_all** | 创建完整备份，保留所有内容 |

### 使用示例

<details>
<summary><b>💻 Windows (PowerShell)</b></summary>

```powershell
# 基本安装
.\install.ps1

# 使用中国镜像 + 自动安装
.\install.ps1 -c -y

# 安装便携式 Python + 自定义路径
.\install.ps1 -p "D:\Tools\Python" -r "D:\RT-Env"

# 指定自定义 env 仓库分支
.\install.ps1 -E "https://github.com/RT-Thread/env.git#master"

# 安装 pyocd + 使用官方源
.\install.ps1 -d -o
```

</details>

<details>
<summary><b>🐧 Linux/macOS (bash)</b></summary>

```bash
# 基本安装
./install.sh

# 使用中国镜像 + 自动安装
./install.sh -c -y

# 指定自定义 packages 仓库
./install.sh -P "https://gitee.com/RT-Thread/packages.git#master"

# 使用备份策略
./install.sh -b preserve

# 指定自定义 sdk 仓库
./install.sh -S "https://github.com/RT-Thread/sdk.git#master"
```

</details>

---

## 💡 使用指南

安装完成后，按照以下步骤开始使用 RT-Thread ENV：

### 步骤 1️⃣：激活环境

<details>
<summary><b>💻 Windows</b></summary>

```powershell
. ~/.rt-env/env.ps1
```

</details>

<details>
<summary><b>🐧 Linux/macOS</b></summary>

```bash
source ~/.rt-env/env.sh
```

</details>

> 💡 **提示**：如需每次启动自动激活，请参考安装章节的自动激活方案。

### 步骤 2️⃣：安装工具链

运行 `sdk` 命令安装开发板所需的工具链：

```bash
sdk
```

### 步骤 3️⃣：使用命令

激活后，可以使用以下命令：

| 命令 | 功能 | 说明 |
|------|------|------|
| `menuconfig` | ⚙️ 配置项目 | 配置 RT-Thread 内核、BSP |
| `menuconfig -s` | 🔧 配置 ENV | 配置软件包、工具 |
| `pkgs` | 📦 包管理器 | 更新、升级软件包 |
| `sdk` | 🛠️ 工具链管理器 | 安装开发工具链 |
| `scons` | 🔨 编译项目 | 构建项目 |

### 步骤 4️⃣：额外工具（可选）

**pyocd** - 用于调试 Cortex-M 设备：

```bash
pip install pyocd
```

### 📚 详细文档

- [Env 工具使用指南](https://github.com/RT-Thread/rt-thread/blob/master/documentation/env/env.md)
- [Env 官方用户手册](https://www.rt-thread.org/document/site/#/development-tools/env/env)

---

## ❓ 常见问题

### 🌐 网络与镜像问题

**问题：下载缓慢或失败**

- ✅ 使用 `--cn` 参数启用 Gitee 镜像
- ✅ 检查网络连接
- ✅ 尝试切换网络环境（如使用 VPN）

### 🔐 权限问题

#### Linux/macOS

Linux 安装脚本会自动使用 `sudo` 提权，通常无需手动处理。

如遇权限问题：

```bash
# 检查 .rt-env 目录权限
ls -la ~/.rt-env

# 如果目录属于 root，修改所有权
sudo chown -R $USER:$USER ~/.rt-env
```

#### Windows

如遇权限错误：

1. ✅ 检查杀毒软件是否阻止安装
2. ✅ 以管理员身份运行 PowerShell
3. ✅ 确保执行策略允许脚本运行

### 📝 其他问题

如遇到其他问题，请：

- 📖 查看 [Env 工具完整文档](https://github.com/RT-Thread/rt-thread/blob/master/documentation/env/env.md)
- 🐛 在 [GitHub Issues](https://github.com/RT-Thread/env/issues) 提交问题
- 💬 加入 [RT-Thread 论坛](https://www.rt-thread.org/qa/forum.html) 寻求帮助

---

## 📖 相关资源

### 官方文档

- [Env 工具完整文档](https://github.com/RT-Thread/rt-thread/blob/master/documentation/env/env.md)
- [QEMU 快速入门](https://github.com/RT-Thread/rt-thread/blob/master/documentation/quick-start/quick_start_qemu/quick_start_qemu_linux.md)
- [BSP 配置说明](https://github.com/RT-Thread/rt-thread/blob/master/documentation/env/env.md#bsp-configuration-menuconfig)

### 相关链接

| 类型 | 链接 |镜像|
|------|------|----|
| 📦 Env 仓库 | [GitHub](https://github.com/RT-Thread/env) |[Gitee](https://gitee.com/RT-Thread-Mirror/env) |
| ![RT-Thread](https://www.rt-thread.org/favicon.ico) RT-Thread 仓库|[GitHub](https://github.com/RT-Thread/rt-thread) |[Gitee](https://gitee.com/rtthread/rt-thread) |
| 🌐 官方网站 | [RT-Thread 官网](https://www.rt-thread.org/) ||
| 📚 文档中心 | [RT-Thread 文档(英文)](https://www.rt-thread.io/document/site/) |[RT-Thread 文档中心(中文)](https://www.rt-thread.org/document/site/#/)|

### 许可证

[![License: GPL-2.0](https://img.shields.io/badge/License-GPL--2.0-blue.svg)](LICENSE)

本项目采用 **GPL-2.0** 许可证开源。

---

<div align="center">

## 🤝 贡献者

感谢所有为 RT-Thread Env 项目做出贡献的开发者！

[![Contributors](https://img.shields.io/github/contributors/RT-Thread/env?style=for-the-badge)](https://github.com/RT-Thread/env/graphs/contributors)

</div>