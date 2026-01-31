<div align="center">

# Python Scripts for RT-Thread Env

[![License: GPL-2.0](https://img.shields.io/badge/License-GPL--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.6+-green.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)]()

**[简体中文](README_ZH.md) | English**

</div>

---

## ⚠️ Version Compatibility Notice

| RT-Thread Version | Recommended Env Version |
|-------------------|------------------------|
| **> v5.1.0** or **master branch** | ✅ **env v2.0** (current version) |
| **≤ v5.1.0** | ⚠️ [env v1.5.x](https://github.com/RT-Thread/env/tree/v1.5.x) (Linux) / [env-windows v1.5.2](https://github.com/RT-Thread/env-windows/tree/v1.5.2) (Windows) |

### 🔄 Key Changes in v2.0

- ✨ **Python Version Upgrade**: Upgraded from Python 2 to Python 3
- 🔧 **Configuration System Refactor**: Replaced kconfig-frontends with Python kconfiglib
- 📦 **Dependency Management Optimization**: Installer automatically handles kconfiglib dependency

> **Note**: env v2.0 is incompatible with kconfiglib from env v1.5.x. If you need to switch versions, please run `pip uninstall kconfiglib` first.

---

## 📚 Table of Contents

- [🚀 Quick Start](#-quick-start)
  - [Windows Installation](#windows-installation)
  - [Linux/macOS Installation](#linuxmacos-installation)
- [⚙️ Installation Script Parameters](#️-installation-script-parameters)
- [💡 Usage Guide](#-usage-guide)
- [❓ Troubleshooting](#-troubleshooting)
- [📖 Resources](#-resources)

---

## 🚀 Quick Start

### Windows Installation

#### Prerequisites

| Item | Requirements |
|------|-------------|
| **Privileges** | 📋 First installation requires **administrator privileges** (to set execution policy and long path support)<br>Subsequent updates can use normal user privileges |
| **PowerShell** | ✅ Windows PowerShell v5.1+<br>✅ PowerShell 7+ |

#### Encoding Compatibility

> ⚠️ **Important Notice**
>
> | PowerShell Version | Encoding Support | Notes |
> |-------------------|------------------|-------|
> | Windows PowerShell (v5.1) | ⚠️ GB2312 default, requires UTF-8 with BOM | Chinese systems require special handling |
> | PowerShell 7+ | ✅ Native UTF-8 | No encoding issues |
>
> Installation scripts are configured as UTF-8 with BOM encoding to ensure compatibility.

#### Installation Commands

<details>
<summary><b>🌐 International Users (Official Source)</b></summary>

```powershell
Set-ExecutionPolicy -ExecutionPolicy Bypass Process; irm https://raw.githubusercontent.com/RT-Thread/env/master/tools/install.ps1 | Out-File -Encoding utf8 .\install.ps1; .\install.ps1; Remove-Item .\install.ps1
```

</details>

<details>
<summary><b>🇨🇳 Users in China (Mirror Source)</b></summary>

```powershell
Set-ExecutionPolicy -ExecutionPolicy Bypass Process; irm https://gitee.com/RT-Thread-Mirror/env/raw/master/tools/install.ps1 | Out-File -Encoding utf8 .\install.ps1; .\install.ps1; Remove-Item .\install.ps1
```

</details>

#### Notes

> 💡 **Tip**: Installation script automatically selects mirror sources based on geographic location. To explicitly specify, use `--cn` or `--official` parameters. See [Installation Script Parameters](#️-installation-script-parameters).

> ⚠️ **Important**:
> - ✅ First installation requires administrator privileges for execution policy and long path support
> - 🦠 Antivirus software may block installation, please temporarily disable if needed

#### Activate Environment

After installation, you need to activate environment variables to use the tools.

<details>
<summary><b>🔧 Option A: Manual Activation (Temporary)</b></summary>

Run the following command each time you start a new PowerShell session:

```powershell
. ~/.rt-env/env.ps1
```

</details>

<details>
<summary><b>⭐ Option B: Auto Activation (Recommended)</b></summary>

Add the activation command to your PowerShell configuration file:

```powershell
# Open configuration file (creates if it doesn't exist)
notepad $PROFILE

# Add the following line:
. ~/.rt-env/env.ps1
```

**Configuration File Paths:**

| PowerShell Version | Configuration File Path |
|-------------------|------------------------|
| Windows PowerShell (v5.1) | `C:\Users\<username>\Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1` |
| PowerShell 7+ | `C:\Users\<username>\Documents\PowerShell\Microsoft.PowerShell_profile.ps1` |

After adding, the environment will be automatically activated each time you open PowerShell.

</details>

### Linux/macOS Installation

#### Installation Commands

<details>
<summary><b>🌐 International Users (Official Source)</b></summary>

```bash
bash -c "$(wget https://raw.githubusercontent.com/RT-Thread/env/master/tools/install.sh -O -)"
```

</details>

<details>
<summary><b>🇨🇳 Users in China (Mirror Source)</b></summary>

```bash
bash -c "$(wget https://gitee.com/RT-Thread-Mirror/env/raw/master/tools/install.sh -O -)" -- --cn
```

</details>

#### Notes

> 💡 **Tips**:
> - Installation script automatically selects mirror sources based on geographic location
> - Linux systems automatically use `sudo` to elevate privileges for installing dependencies, no need to manually run as root
> - Supports installation with normal user privileges, script automatically handles privilege elevation

#### Activate Environment

<details>
<summary><b>🔧 Option A: Manual Activation (Temporary)</b></summary>

Run the following command each time you open a new terminal:

```bash
source ~/.rt-env/env.sh
```

</details>

<details>
<summary><b>⭐ Option B: Auto Activation (Recommended)</b></summary>

Add the activation command to your shell configuration file:

```bash
# For bash
echo 'source ~/.rt-env/env.sh' >> ~/.bashrc

# For zsh
echo 'source ~/.rt-env/env.sh' >> ~/.zshrc
```

After adding, the environment will be automatically activated each time you log in.

</details>

#### 📚 Related Tutorials

- [Install Env with QEMU Simulator in Ubuntu](https://github.com/RT-Thread/rt-thread/blob/master/documentation/quick-start/quick_start_qemu/quick_start_qemu_linux.md)

---

## ⚙️ Installation Script Parameters

| Parameter | Description |
|-----------|-------------|
| **Basic Parameters**||
| `-y`, `--yes`, `--auto` | Automatic installation, no interaction |
| `-h`, `--help` | Display help information |
|**Source Settings**||
| `-c`, `--cn`, `--gitee` | Use China mirror sources (Gitee, PyPI TUNA) |
| `-o`, `--official` | Force use of official sources |
| **Repository Configuration**||
| `-P`, `--packages <repo>[#<branch>]` | Specify packages repository address and branch |
| `-E`, `--env <repo>[#<branch>]` | Specify env repository address and branch |
| `-S`, `--sdk <repo>[#<branch>]` | Specify sdk repository address and branch |
| `-t`, `--touch-env-url <url>` | Specify touch_env.py download URL |
|**Path & Installation**||
| `-r`, `--env-root <path>` | Set custom .rt-env directory path (default: `~/.rt-env`) |
| `-p`, `--python [path]` | Install portable Python, installation directory is path (Windows only, default: D:\Tools\Python) |
|**Other Options**||
| `-d`, `--pyocd` | Install pyocd (for debugging) |
| `-e`, `--en`, `--english` | Force English display |
| `-z`, `--zh`, `--chinese` | Force Chinese display |
| `-b`, `--backup <strategy>` | Backup strategy |

### Backup Strategies

| Strategy | Description |
|----------|-------------|
| **preserve** (default) | Keep configuration files (.config) and toolchains (local_pkgs), delete other content |
| **delete_all** | Backup then delete existing ENV directory |
| **delete_all_now** | Immediately delete existing ENV directory, no backup |
| **backup_all** | Create full backup, keep all content |

### Usage Examples

<details>
<summary><b>💻 Windows (PowerShell)</b></summary>

```powershell
# Basic installation
.\install.ps1

# Use China mirror + automatic installation
.\install.ps1 -c -y

# Install portable Python + custom path
.\install.ps1 -p "D:\Tools\Python" -r "D:\RT-Env"

# Specify custom env repository branch
.\install.ps1 -E "https://github.com/RT-Thread/env.git#master"

# Install pyocd + official source
.\install.ps1 -d -o
```

</details>

<details>
<summary><b>🐧 Linux/macOS (bash)</b></summary>

```bash
# Basic installation
./install.sh

# Use China mirror + automatic installation
./install.sh -c -y

# Specify custom packages repository
./install.sh -P "https://gitee.com/RT-Thread/packages.git#master"

# Use backup strategy
./install.sh -b preserve

# Specify custom sdk repository
./install.sh -S "https://github.com/RT-Thread/sdk.git#master"
```

</details>

---

## 💡 Usage Guide

After installation completes, follow these steps to start using RT-Thread ENV:

### Step 1️⃣: Activate Environment

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

> 💡 **Tip**: For auto-activation on startup, please refer to the auto-activation options in the installation section.

### Step 2️⃣: Install Toolchains

Run the `sdk` command to install required toolchains for your development board:

```bash
sdk
```

### Step 3️⃣: Use Commands

After activation, you can use the following commands:

| Command | Function | Description |
|---------|----------|-------------|
| `menuconfig` | ⚙️ Configure Project | Configure RT-Thread kernel, BSP |
| `menuconfig -s` | 🔧 Configure ENV | Configure packages, tools |
| `pkgs` | 📦 Package Manager | Update, upgrade packages |
| `sdk` | 🛠️ Toolchain Manager | Install development toolchains |
| `scons` | 🔨 Build Project | Build project |

### Step 4️⃣: Additional Tools (Optional)

**pyocd** - For debugging Cortex-M devices:

```bash
pip install pyocd
```

### 📚 Detailed Documentation

- [Env Tool Usage Guide](https://github.com/RT-Thread/rt-thread/blob/master/documentation/env/env.md)
- [Env Official User Manual](https://www.rt-thread.org/document/site/#/development-tools/env/env)

---

## ❓ Troubleshooting

### 🌐 Network & Mirror Issues

**Problem: Slow download or failure**

- ✅ Use `--cn` parameter to enable Gitee mirror
- ✅ Check network connection
- ✅ Try switching network environment (e.g., using VPN)

### 🔐 Permission Issues

#### Linux/macOS

Linux installation script automatically uses `sudo` for privilege elevation, usually no manual handling needed.

If you encounter permission issues:

```bash
# Check .rt-env directory permissions
ls -la ~/.rt-env

# If directory belongs to root, change ownership
sudo chown -R $USER:$USER ~/.rt-env
```

#### Windows

If you encounter permission errors:

1. ✅ Check if antivirus software is blocking installation
2. ✅ Run PowerShell as administrator
3. ✅ Ensure execution policy allows script running

### 📝 Other Issues

If you encounter other issues, please:

- 📖 Check [Env Tool Complete Documentation](https://github.com/RT-Thread/rt-thread/blob/master/documentation/env/env.md)
- 🐛 Submit issue on [GitHub Issues](https://github.com/RT-Thread/env/issues)
- 💬 Join [RT-Thread Forum](https://www.rt-thread.org/qa/forum.html) for help

---

## 📖 Resources

### Official Documentation

- [Env Tool Complete Documentation](https://github.com/RT-Thread/rt-thread/blob/master/documentation/env/env.md)
- [QEMU Quick Start](https://github.com/RT-Thread/rt-thread/blob/master/documentation/quick-start/quick_start_qemu/quick_start_qemu_linux.md)
- [BSP Configuration Guide](https://github.com/RT-Thread/rt-thread/blob/master/documentation/env/env.md#bsp-configuration-menuconfig)

### Related Links

| Type | Link | Mirror |
|------|------|--------|
| 📦 Env Repository | [GitHub](https://github.com/RT-Thread/env) | [Gitee](https://gitee.com/RT-Thread-Mirror/env) |
| ![RT-Thread](https://www.rt-thread.org/favicon.ico) RT-Thread Repository | [GitHub](https://github.com/RT-Thread/rt-thread) | [Gitee](https://gitee.com/rtthread/rt-thread) |
| 🌐 Official Website | [RT-Thread Website](https://www.rt-thread.org/) ||
| 📚 Documentation | [RT-Thread Docs (EN)](https://www.rt-thread.io/document/site/) | [RT-Thread Docs (CN)](https://www.rt-thread.org/document/site/#/) |

### License

[![License: GPL-2.0](https://img.shields.io/badge/License-GPL--2.0-blue.svg)](LICENSE)

This project is open-sourced under the **GPL-2.0** license.

---

<div align="center">

## 🤝 Contributors

Thanks to all developers who have contributed to the RT-Thread Env project!

[![Contributors](https://img.shields.io/github/contributors/RT-Thread/env?style=for-the-badge)](https://github.com/RT-Thread/env/graphs/contributors)

</div>